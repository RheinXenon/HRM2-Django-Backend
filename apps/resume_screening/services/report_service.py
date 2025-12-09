"""
报告生成服务模块。
"""
import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from django.conf import settings
from django.core.files.base import ContentFile

from apps.common.utils import ensure_dir, sanitize_filename

logger = logging.getLogger(__name__)


class ReportService:
    """生成和管理筛选报告的服务类。"""
    
    @classmethod
    def generate_md_report(
        cls,
        candidate_name: str,
        conversation_history: List[Dict],
        extracted_data: Dict
    ) -> str:
        """
        从对话历史生成Markdown报告。
        
        参数:
            candidate_name: 候选人名称
            conversation_history: 对话消息列表
            extracted_data: 提取的分数和评论
            
        返回:
            Markdown内容字符串
        """
        lines = []
        
        # 标题
        lines.append(f"# {candidate_name} 简历初筛报告\n")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append("\n---\n")
        
        # 分数汇总
        lines.append("## 评分汇总\n")
        scores = extracted_data.get('scores', {})
        lines.append("| 维度 | 评分 |\n")
        lines.append("|------|------|\n")
        lines.append(f"| HR评分 | {scores.get('hr_score', 0)} |\n")
        lines.append(f"| 技术评分 | {scores.get('technical_score', 0)} |\n")
        lines.append(f"| 管理评分 | {scores.get('manager_score', 0)} |\n")
        lines.append(f"| **综合评分** | **{scores.get('comprehensive_score', 0)}** |\n")
        lines.append("\n")
        
        # 薪资建议
        salary = extracted_data.get('salary_suggestions', {})
        if salary.get('final_suggestion'):
            lines.append(f"**建议月薪**: {salary.get('final_suggestion')}\n\n")
        
        # 最终推荐
        recommendation = extracted_data.get('final_recommendation', {})
        if recommendation.get('decision'):
            lines.append(f"**招聘建议**: {recommendation.get('decision')}\n\n")
        
        # 详细评审记录
        lines.append("## 详细评审记录\n")
        for message in conversation_history:
            speaker = message.get('name', 'Unknown')
            content = message.get('content', '')
            
            lines.append(f"### {speaker}\n\n")
            lines.append(f"{content}\n\n")
            lines.append("---\n\n")
        
        return "".join(lines)
    
    @classmethod
    def generate_json_report(
        cls,
        candidate_name: str,
        extracted_data: Dict,
        conversation_history: List[Dict] = None
    ) -> str:
        """
        从提取的数据生成JSON报告。
        
        参数:
            candidate_name: 候选人名称
            extracted_data: 提取的分数和评论
            conversation_history: 可选的对话历史
            
        返回:
            JSON字符串
        """
        report_data = {
            "file_name": f"{candidate_name}简历初筛结果.md",
            "name": candidate_name,
            "generated_at": datetime.now().isoformat(),
            "scores": extracted_data.get("scores", {}),
            "salary_suggestions": extracted_data.get("salary_suggestions", {}),
            "review_comments": extracted_data.get("review_comments", {}),
            "final_recommendation": extracted_data.get("final_recommendation", {})
        }
        
        if conversation_history:
            report_data["conversation_history"] = conversation_history
        
        return json.dumps(report_data, ensure_ascii=False, indent=2)
    
    @classmethod
    def save_report_to_model(
        cls,
        task,
        candidate_name: str,
        md_content: str,
        json_content: str,
        resume_content: str = ""
    ):
        """
        将报告保存到数据库。
        
        参数:
            task: ResumeScreeningTask实例
            candidate_name: 候选人名称
            md_content: Markdown报告内容
            json_content: JSON报告内容
            resume_content: 原始简历内容
            
        返回:
            ScreeningReport实例
        """
        from ..models import ScreeningReport
        
        # 创建报告
        filename = f"{sanitize_filename(candidate_name)}简历初筛结果.md"
        
        report = ScreeningReport.objects.create(
            task=task,
            original_filename=filename,
            resume_content=resume_content,
            json_report_content=json_content
        )
        
        # 保存MD文件
        report.md_file.save(filename, ContentFile(md_content.encode('utf-8')))
        
        return report
    
    @classmethod
    def save_or_update_resume_data(
        cls,
        task,
        position_data: Dict,
        candidate_name: str,
        resume_content: str,
        screening_result: Dict = None
    ):
        """
        将简历数据保存到统一管理表，如果已存在则更新筛选结果。
        
        参数:
            task: ResumeScreeningTask实例
            position_data: 岗位信息
            candidate_name: 候选人名称
            resume_content: 简历内容
            screening_result: 包含分数和报告的筛选结果（可选）
            
        返回:
            tuple: (ResumeData实例, 是否为新创建)
        """
        from ..models import ResumeData
        from apps.common.utils import generate_hash
        
        # 生成哈希：仅基于简历内容，相同内容的简历会有相同哈希值用于去重
        resume_hash = generate_hash(resume_content)
        
        # 检查是否已存在相同哈希的简历
        existing = ResumeData.objects.filter(resume_file_hash=resume_hash).first()
        
        if existing:
            # 如果存在，更新关联任务和筛选结果（如果有）
            if existing.task is None:  # 只有在没有关联任务时才更新
                existing.task = task
                existing.save()
            
            # 如果提供了筛选结果，更新相关字段
            if screening_result:
                existing.screening_score = screening_result.get('scores', {})
                existing.screening_summary = screening_result.get('summary', '')
                existing.json_report_content = screening_result.get('json_content', '')
                
                # 保存报告文件（如果提供）
                md_content = screening_result.get('md_content')
                if md_content:
                    md_filename = f"{sanitize_filename(candidate_name)}简历初筛结果.md"
                    existing.report_md_file.save(md_filename, ContentFile(md_content.encode('utf-8')), save=False)
                
                json_content = screening_result.get('json_content')
                if json_content:
                    json_filename = f"{sanitize_filename(candidate_name)}.json"
                    existing.report_json_file.save(json_filename, ContentFile(json_content.encode('utf-8')), save=False)
                
                existing.save()  # 保存所有更改
                logger.info(f"更新现有简历数据（哈希: {resume_hash[:8]}...）的筛选结果")
            
            return existing, False  # 返回现有记录，标记为非新建
        
        # 创建新记录
        resume_data = ResumeData.objects.create(
            task=task,
            position_title=position_data.get('position', '未知职位'),
            position_details=position_data,
            candidate_name=candidate_name,
            resume_content=resume_content,
            resume_file_hash=resume_hash,
            screening_score=screening_result.get('scores', {}) if screening_result else {},
            screening_summary=screening_result.get('summary', '') if screening_result else '',
            json_report_content=screening_result.get('json_content', '') if screening_result else ''
        )
        
        # 如果提供了内容则保存报告文件
        if screening_result:
            md_content = screening_result.get('md_content')
            if md_content:
                md_filename = f"{sanitize_filename(candidate_name)}简历初筛结果.md"
                resume_data.report_md_file.save(md_filename, ContentFile(md_content.encode('utf-8')), save=False)
            
            json_content = screening_result.get('json_content')
            if json_content:
                json_filename = f"{sanitize_filename(candidate_name)}.json"
                resume_data.report_json_file.save(json_filename, ContentFile(json_content.encode('utf-8')), save=False)
            
            resume_data.save()  # 保存文件字段
        
        return resume_data, True  # 返回新创建的记录，标记为新建

    @classmethod
    def save_resume_data(
        cls,
        task,
        position_data: Dict,
        candidate_name: str,
        resume_content: str,
        screening_result: Dict
    ):
        """
        将简历数据保存到统一管理表。
        
        参数:
            task: ResumeScreeningTask实例
            position_data: 岗位信息
            candidate_name: 候选人名称
            resume_content: 简历内容
            screening_result: 包含分数和报告的筛选结果
            
        返回:
            tuple: (ResumeData实例, 是否为新创建)
        """
        return cls.save_or_update_resume_data(
            task=task,
            position_data=position_data,
            candidate_name=candidate_name,
            resume_content=resume_content,
            screening_result=screening_result
        )
