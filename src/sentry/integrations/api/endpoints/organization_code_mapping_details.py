from django.db.models.deletion import ProtectedError
from django.http import Http404
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from sentry.api.api_owners import ApiOwner
from sentry.api.api_publish_status import ApiPublishStatus
from sentry.api.base import region_silo_endpoint
from sentry.api.bases.organization import (
    OrganizationEndpoint,
    OrganizationIntegrationsLoosePermission,
)
from sentry.api.serializers import serialize
from sentry.integrations.models.repository_project_path_config import RepositoryProjectPathConfig
from sentry.integrations.services.integration import integration_service

from .organization_code_mappings import (
    OrganizationIntegrationMixin,
    RepositoryProjectPathConfigSerializer,
)


@region_silo_endpoint
class OrganizationCodeMappingDetailsEndpoint(OrganizationEndpoint, OrganizationIntegrationMixin):
    owner = ApiOwner.ISSUES
    publish_status = {
        "DELETE": ApiPublishStatus.PRIVATE,
        "PUT": ApiPublishStatus.PRIVATE,
    }
    permission_classes = (OrganizationIntegrationsLoosePermission,)

    def convert_args(self, request: Request, organization_id_or_slug, config_id, *args, **kwargs):
        args, kwargs = super().convert_args(
            request, organization_id_or_slug, config_id, *args, **kwargs
        )
        ois = integration_service.get_organization_integrations(
            organization_id=kwargs["organization"].id
        )
        try:
            kwargs["config"] = RepositoryProjectPathConfig.objects.get(
                id=config_id,
                organization_integration_id__in=[oi.id for oi in ois],
            )
        except RepositoryProjectPathConfig.DoesNotExist:
            raise Http404

        if request.data.get("projectId"):
            kwargs["new_project"] = super().get_project(
                kwargs["organization"], request.data.get("projectId")
            )

        return (args, kwargs)

    def put(self, request: Request, config_id, organization, config, new_project) -> Response:
        """
        Update a repository project path config
        ``````````````````

        :pparam string organization_id_or_slug: the id or slug of the organization the
                                          team should be created for.
        :param int repository_id:
        :param int project_id:
        :param string stack_root:
        :param string source_root:
        :param string default_branch:
        :auth: required
        """
        if not request.access.has_projects_access([config.project, new_project]):
            return self.respond(status=status.HTTP_403_FORBIDDEN)

        try:
            # We expect there to exist an org_integration
            org_integration = self.get_organization_integration(organization, config.integration_id)
        except Http404:
            # Human friendly error response.
            return self.respond(
                "Could not find this integration installed on your organization",
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = RepositoryProjectPathConfigSerializer(
            context={
                "organization": organization,
                "organization_integration": org_integration,
            },
            instance=config,
            data=request.data,
        )
        if serializer.is_valid():
            repository_project_path_config = serializer.save()
            return self.respond(
                serialize(repository_project_path_config, request.user),
                status=status.HTTP_200_OK,
            )
        return self.respond(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request: Request, config_id, organization, config) -> Response:
        """
        Delete a repository project path config

        :auth: required
        """

        if not request.access.has_project_access(config.project):
            return self.respond(status=status.HTTP_403_FORBIDDEN)

        try:
            config.delete()
            return self.respond(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return self.respond(
                "Cannot delete Code Mapping. Must delete Code Owner that uses this mapping first.",
                status=status.HTTP_409_CONFLICT,
            )
