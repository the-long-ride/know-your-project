from know_your_project.domain.ids import ProjectId
from .principal import Principal


class AuthorizationError(PermissionError):
    pass


class AuthorizationService:
    def require_project(self, principal: Principal, project: ProjectId) -> None:
        if project not in principal.projects:
            raise AuthorizationError(f"project access denied: {project}")
