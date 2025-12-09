"""
简历筛选API视图模块 - 与原版 RecruitmentSystemAPI 返回格式保持一致。
"""
import logging
from django.conf import settings
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status

from apps.common.mixins import SafeAPIView
from apps.common.exceptions import ValidationException

from ..models import ResumeScreeningTask, ScreeningReport, ResumeData
from ..services import ScreeningService, ReportService
from ..serializers import ResumeScreeningInputSerializer

logger = logging.getLogger(__name__)


class ResumeScreeningView(SafeAPIView):
    """
    简历初筛API
    POST: 提交简历筛选任务
    """
    
    def handle_post(self, request):
        """提交简历筛选任务。"""
        # 验证输入
        serializer = ResumeScreeningInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "参数验证失败", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # 解析输入数据
            position_data, resumes_data = ScreeningService.parse_input_data(request.data)
            
            # 创建任务
            task = ResumeScreeningTask.objects.create(
                status='pending',
                progress=0,
                total_steps=len(resumes_data),
                current_step=0,
                position_data=position_data
            )
            
            # 立即保存简历数据，确保即使任务失败也能获取简历内容
            from apps.common.utils import extract_name_from_filename
            for resume in resumes_data:
                candidate_name = extract_name_from_filename(resume['name'])
                ReportService.save_or_update_resume_data(
                    task=task,
                    position_data=position_data,
                    candidate_name=candidate_name,
                    resume_content=resume['content'],
                    screening_result=None  # 初始时没有筛选结果
                )
            
            # 启动异步任务（使用Celery或线程）
            self._start_screening_task(task, position_data, resumes_data)
            
            # 返回与原版一致的格式
            return Response({
                "status": "submitted",
                "message": "简历筛选任务已提交，正在后台处理",
                "task_id": str(task.id)
            }, status=status.HTTP_202_ACCEPTED)
            
        except ValidationException as e:
            return Response(
                {"error": e.message, "details": e.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _start_screening_task(self, task, position_data, resumes_data):
        """在后台启动筛选任务（使用线程）。"""
        import threading
        thread = threading.Thread(
            target=self._run_screening_sync,
            args=(task, position_data, resumes_data)
        )
        thread.daemon = True
        thread.start()
        logger.info(f"Started thread for screening task {task.id}")
    
    def _run_screening_sync(self, task, position_data, resumes_data):
        """同步运行筛选（用于线程回退）。"""
        from apps.common.utils import extract_name_from_filename
        from django.core.cache import cache
        
        try:
            # 检查是否设置了强制错误标志（测试钩子）
            error_config = cache.get('test_force_screening_error')
            if error_config and error_config.get('active', False):
                error_message = error_config.get('message', '测试：强制触发的简历筛选任务失败')
                error_type = error_config.get('type', 'runtime')
                
                logger.info(f"Force error trigger: {error_message} (type: {error_type})")
                
                if error_type == 'validation':
                    from apps.common.exceptions import ValidationException
                    raise ValidationException(error_message)
                elif error_type == 'service':
                    from apps.common.exceptions import ServiceException
                    raise ServiceException(error_message)
                else:  # runtime
                    raise RuntimeError(error_message)
            
            task.status = 'running'
            task.save()
            
            results = ScreeningService.run_screening(
                task=task,
                position_data=position_data,
                resumes_data=resumes_data,
                run_chat=True
            )
            
            # 保存结果，跟踪重复简历
            new_count = 0
            duplicate_count = 0
            
            for resume in resumes_data:
                candidate_name = extract_name_from_filename(resume['name'])
                result = results.get(candidate_name, {})
                
                # 更新或创建简历数据（即使没有结果也要确保简历数据存在）
                resume_data, is_new = ReportService.save_or_update_resume_data(
                    task=task,
                    position_data=position_data,
                    candidate_name=candidate_name,
                    resume_content=resume['content'],
                    screening_result=result if result else None
                )
                
                if is_new:
                    new_count += 1
                else:
                    duplicate_count += 1
            
            # 记录统计信息
            if duplicate_count > 0:
                logger.info(f"筛选完成: {new_count} 份新简历, {duplicate_count} 份重复简历已跳过")
            
            task.status = 'completed'
            task.progress = 100
            task.current_step = task.total_steps
            task.current_speaker = None
            task.save()
            
        except Exception as e:
            logger.error(f"Screening failed: {e}", exc_info=True)
            task.status = 'failed'
            task.error_message = str(e)
            task.current_speaker = None
            task.save()


class ScreeningTaskStatusView(SafeAPIView):
    """
    查询筛选任务状态API
    GET: 获取任务状态和结果
    """
    
    def handle_get(self, request, task_id):
        """获取任务状态。"""
        task = self.get_object_or_404(ResumeScreeningTask, id=task_id)
        
        response_data = {
            "task_id": str(task.id),
            "status": task.status,
            "progress": task.progress,
            "current_step": task.current_step,
            "total_steps": task.total_steps,
            "created_at": task.created_at.isoformat()
        }
        
        # 如果正在运行则添加当前发言者
        if task.status == 'running' and task.current_speaker:
            response_data['current_speaker'] = task.current_speaker
        
            # 无论任务状态如何，都获取简历数据
            response_data['resume_data'] = self._get_resume_data(task)
            
            # 如果已完成则添加结果
            if task.status == 'completed':
                response_data['reports'] = self._get_reports(task)
        
        # 如果失败则添加错误信息
        if task.status == 'failed' and task.error_message:
            response_data['error_message'] = task.error_message
        
        # 返回与原版一致的格式
        return JsonResponse(response_data)
    
    def _get_reports(self, task):
        """获取任务的报告。"""
        reports = ScreeningReport.objects.filter(task=task)
        return [
            {
                "report_id": str(report.id),
                "report_filename": report.original_filename,
                "download_url": f"/resume-screening/reports/{report.id}/download/",
                "resume_content": report.resume_content or ""
            }
            for report in reports
        ]
    
    def _get_resume_data(self, task):
        """获取任务的简历数据。"""
        resume_data_list = ResumeData.objects.filter(task=task)
        result = []
        
        for resume_data in resume_data_list:
            data = {
                "id": str(resume_data.id),
                "candidate_name": resume_data.candidate_name,
                "position_title": resume_data.position_title,
                "scores": resume_data.screening_score,
                "summary": resume_data.screening_summary,
                "json_content": resume_data.json_report_content,
                "resume_content": resume_data.resume_content,
                "report_md_url": resume_data.report_md_file.url if resume_data.report_md_file else None,
                "report_json_url": resume_data.report_json_file.url if resume_data.report_json_file else None,
            }
            
            # 如果存在则添加视频分析
            if resume_data.video_analysis:
                data["video_analysis"] = {
                    "video_id": str(resume_data.video_analysis.id),
                    "video_name": resume_data.video_analysis.video_name,
                    "status": resume_data.video_analysis.status,
                    "confidence_score": resume_data.video_analysis.confidence_score,
                }
            
            result.append(data)
        
        return result
