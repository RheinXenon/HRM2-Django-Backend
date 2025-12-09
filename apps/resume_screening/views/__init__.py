from .screening import ResumeScreeningView, ScreeningTaskStatusView
from .resume_data import ResumeDataView, ResumeDataDetailView
from .resume_group import (
    ResumeGroupListView, 
    ResumeGroupDetailView,
    CreateResumeGroupView,
    AddResumeToGroupView,
    RemoveResumeFromGroupView,
    SetGroupStatusView
)
from .task import TaskHistoryView, TaskDeleteView, ReportDownloadView
from .link import LinkResumeVideoView, UnlinkResumeVideoView
from .resume_library import (
    ResumeLibraryListView,
    ResumeLibraryDetailView,
    ResumeLibraryBatchDeleteView,
    ResumeLibraryCheckHashView
)
from .dev_tools import GenerateRandomResumesView, ForceScreeningErrorView, ResetScreeningTestStateView

__all__ = [
    'ResumeScreeningView',
    'ScreeningTaskStatusView',
    'ResumeDataView',
    'ResumeDataDetailView',
    'ResumeGroupListView',
    'ResumeGroupDetailView',
    'CreateResumeGroupView',
    'AddResumeToGroupView',
    'RemoveResumeFromGroupView',
    'SetGroupStatusView',
    'TaskHistoryView',
    'TaskDeleteView',
    'ReportDownloadView',
    'LinkResumeVideoView',
    'UnlinkResumeVideoView',
    'ResumeLibraryListView',
    'ResumeLibraryDetailView',
    'ResumeLibraryBatchDeleteView',
    'ResumeLibraryCheckHashView',
    # 开发测试工具
    'GenerateRandomResumesView',
    'ForceScreeningErrorView',
    'ResetScreeningTestStateView',
]
