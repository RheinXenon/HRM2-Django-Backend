"""
开发测试工具视图模块。
提供开发辅助API，如生成随机简历等。
"""
import logging
from django.http import JsonResponse

from apps.common.mixins import SafeAPIView
from apps.common.exceptions import ValidationException
from apps.resume_screening.models import ResumeLibrary

logger = logging.getLogger(__name__)


class GenerateRandomResumesView(SafeAPIView):
    """
    生成随机简历API
    POST: 根据岗位要求生成随机简历并添加到简历库
    """
    
    def handle_post(self, request):
        """生成随机简历并添加到简历库"""
        from services.agents import get_dev_tools_service
        
        data = request.data
        position_data = data.get('position', {})
        count = data.get('count', 5)
        
        if not position_data:
            raise ValidationException("请提供岗位信息")
        
        if not position_data.get('position'):
            raise ValidationException("请提供岗位名称")
        
        # 限制数量
        count = max(1, min(20, int(count)))
        
        try:
            service = get_dev_tools_service()
            resumes = service.generate_batch_resumes(position_data, count)
            
            # 添加到简历库
            added_resumes = []
            skipped_resumes = []
            
            for resume in resumes:
                # 检查哈希是否已存在
                if ResumeLibrary.objects.filter(file_hash=resume['file_hash']).exists():
                    skipped_resumes.append({
                        'filename': resume['name'],
                        'reason': '哈希值已存在'
                    })
                    continue
                
                # 创建简历库记录
                library_entry = ResumeLibrary.objects.create(
                    filename=resume['name'],
                    file_hash=resume['file_hash'],
                    file_size=len(resume['content'].encode('utf-8')),
                    file_type='text/plain',
                    content=resume['content'],
                    candidate_name=resume['candidate_name'],
                    is_screened=False,
                    is_assigned=False,
                    notes=f"由开发测试工具自动生成，目标岗位：{position_data.get('position', '未知')}"
                )
                
                added_resumes.append({
                    'id': str(library_entry.id),
                    'filename': library_entry.filename,
                    'candidate_name': library_entry.candidate_name
                })
            
            return JsonResponse({
                'code': 200,
                'message': f'成功生成 {len(added_resumes)} 份简历',
                'data': {
                    'added': added_resumes,
                    'skipped': skipped_resumes,
                    'added_count': len(added_resumes),
                    'skipped_count': len(skipped_resumes),
                    'requested_count': count
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to generate resumes: {e}")
            raise ValidationException(f"生成简历失败: {str(e)}")


class ForceScreeningErrorView(SafeAPIView):
    """
    强制简历筛选任务失败测试钩子
    POST: 通过环境变量控制是否强制筛选任务失败
    """
    
    def handle_post(self, request):
        """设置/取消强制筛选任务失败的标志"""
        from django.core.cache import cache
        
        data = request.data
        force_error = data.get('force_error', True)
        error_message = data.get('error_message', '测试：强制触发的简历筛选任务失败')
        error_type = data.get('error_type', 'runtime')  # runtime, validation, service
        
        # 设置缓存，影响后续的筛选任务
        cache.set('test_force_screening_error', {
            'active': force_error,
            'message': error_message,
            'type': error_type
        }, timeout=3600)  # 1小时后过期
        
        status_text = "启用" if force_error else "禁用"
        return JsonResponse({
            'code': 200,
            'message': f'已{status_text}强制筛选任务失败测试钩子',
            'data': {
                'force_error': force_error,
                'error_message': error_message,
                'error_type': error_type,
                'expires_in': 3600  # 秒
            }
        })
    
    def handle_get(self, request):
        """查询当前强制错误状态"""
        from django.core.cache import cache
        
        error_config = cache.get('test_force_screening_error')
        
        if not error_config or not error_config.get('active', False):
            return JsonResponse({
                'code': 200,
                'message': '当前未启用强制错误钩子',
                'data': {
                    'active': False
                }
            })
        
        return JsonResponse({
            'code': 200,
            'message': '当前已启用强制错误钩子',
            'data': {
                'active': True,
                'error_message': error_config.get('message'),
                'error_type': error_config.get('type'),
                'remaining_seconds': cache.ttl('test_force_screening_error')
            }
        })


class ResetScreeningTestStateView(SafeAPIView):
    """
    重置简历筛选测试状态
    POST: 清除所有测试相关的缓存和状态
    """
    
    def handle_post(self, request):
        """重置所有测试状态"""
        from django.core.cache import cache
        
        # 清除强制错误标志
        cache.delete('test_force_screening_error')
        
        return JsonResponse({
            'code': 200,
            'message': '已重置所有简历筛选测试状态'
        })
