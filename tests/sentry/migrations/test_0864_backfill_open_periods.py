from sentry.models.activity import Activity
from sentry.models.group import Group, GroupStatus
from sentry.models.groupopenperiod import GroupOpenPeriod
from sentry.models.organization import Organization
from sentry.testutils.cases import TestMigrations
from sentry.types.activity import ActivityType
from sentry.types.group import GroupSubStatus


class BackfillGroupOpenPeriodsTest(TestMigrations):
    migrate_from = "0863_update_organization_member_invite_model"
    migrate_to = "0864_backfill_open_periods"

    def setup_before_migration(self, app):
        self.organization = Organization.objects.create(name="test", slug="test")
        self.project = self.create_project(organization=self.organization)

        # Create a group that has been resolved and then regressed and resolved again
        self.group_resolved = Group.objects.create(
            project=self.project,
            status=GroupStatus.UNRESOLVED,
            substatus=GroupSubStatus.NEW,
        )
        self.group_resolved.update(status=GroupStatus.RESOLVED, substatus=None)
        self.group_resolved_resolution_activity_1 = Activity.objects.create(
            group=self.group_resolved,
            project=self.project,
            type=ActivityType.SET_RESOLVED.value,
        )
        self.group_resolved.update(
            status=GroupStatus.UNRESOLVED, substatus=GroupSubStatus.REGRESSED
        )
        Activity.objects.create(
            group=self.group_resolved,
            project=self.project,
            type=ActivityType.SET_ONGOING.value,
        )
        self.group_resolved.update(status=GroupStatus.RESOLVED, substatus=None)
        self.group_resolved_resolution_activity_2 = Activity.objects.create(
            group=self.group_resolved,
            project=self.project,
            type=ActivityType.SET_RESOLVED.value,
        )
        assert self.group_resolved.status == GroupStatus.RESOLVED
        assert self.group_resolved.substatus is None

        # Create a group that has been resolved and then regressed
        self.group_regressed = Group.objects.create(
            project=self.project,
            status=GroupStatus.UNRESOLVED,
            substatus=GroupSubStatus.NEW,
        )
        self.group_regressed.update(status=GroupStatus.RESOLVED, substatus=None)
        self.group_regressed_resolution_activity = Activity.objects.create(
            group=self.group_regressed,
            project=self.project,
            type=ActivityType.SET_RESOLVED.value,
        )
        self.group_regressed.update(status=GroupStatus.ONGOING, substatus=GroupSubStatus.REGRESSED)
        Activity.objects.create(
            group=self.group_regressed,
            project=self.project,
            type=ActivityType.SET_REGRESSION.value,
        )
        assert self.group_regressed.status == GroupStatus.ONGOING
        assert self.group_regressed.substatus == GroupSubStatus.REGRESSED

        # Create a new group that has never been resolved
        self.group_new = Group.objects.create(
            project=self.project,
            status=GroupStatus.UNRESOLVED,
            substatus=GroupSubStatus.NEW,
        )
        assert self.group_new.status == GroupStatus.UNRESOLVED
        assert self.group_new.substatus == GroupSubStatus.NEW

        # Create a group that has been ignored until escalating
        self.group_ignored = Group.objects.create(
            project=self.project,
            status=GroupStatus.UNRESOLVED,
            substatus=GroupSubStatus.NEW,
        )
        self.group_ignored.update(
            status=GroupStatus.IGNORED, substatus=GroupSubStatus.UNTIL_ESCALATING
        )
        Activity.objects.create(
            group=self.group_ignored,
            project=self.project,
            type=ActivityType.SET_IGNORED.value,
        )
        assert self.group_ignored.status == GroupStatus.IGNORED
        assert self.group_ignored.substatus == GroupSubStatus.UNTIL_ESCALATING

    def test(self):
        self.group_resolved.refresh_from_db()
        open_periods = GroupOpenPeriod.objects.filter(group=self.group_resolved)
        assert len(open_periods) == 2
        assert open_periods[0].date_started == self.group_resolved.first_seen
        assert open_periods[0].date_ended == self.group_resolved_resolution_activity_1.datetime
        assert open_periods[1].date_started > open_periods[0].date_started
        assert open_periods[1].date_ended == self.group_resolved_resolution_activity_2.datetime
        assert open_periods[1].resolution_activity == self.group_resolved_resolution_activity_2

        self.group_regressed.refresh_from_db()
        open_periods = GroupOpenPeriod.objects.filter(group=self.group_regressed)
        assert len(open_periods) == 2
        assert open_periods[0].date_started == self.group_regressed.first_seen
        assert open_periods[0].date_ended == self.group_regressed_resolution_activity_1.datetime
        assert open_periods[1].date_started > open_periods[0].date_started
        assert open_periods[1].date_ended is None
        assert open_periods[1].resolution_activity is None

        self.group_new.refresh_from_db()
        open_periods = GroupOpenPeriod.objects.filter(group=self.group_new)
        assert len(open_periods) == 1
        assert open_periods[0].date_started == self.group_new.first_seen
        assert open_periods[0].date_ended is None
        assert open_periods[0].resolution_activity is None

        self.group_ignored.refresh_from_db()
        open_periods = GroupOpenPeriod.objects.filter(group=self.group_ignored)
        assert len(open_periods) == 1
        assert open_periods[0].date_started == self.group_ignored.first_seen
        assert open_periods[0].date_ended is None
        assert open_periods[0].resolution_activity is None
