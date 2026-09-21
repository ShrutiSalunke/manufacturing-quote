from django.core.management.base import BaseCommand

from apps.access.services import seed_access_control


class Command(BaseCommand):
    help = (
        "Seed RBAC permissions and system roles, and map legacy User.role "
        "to UserRole when a user has no access roles yet."
    )

    def handle(self, *args, **options):
        result = seed_access_control()
        self.stdout.write(
            self.style.SUCCESS(
                "Access control seeded: "
                f"permissions_created={result['permissions_created']}, "
                f"roles={result['roles']}, "
                f"users_mapped={result['users_mapped']}"
            )
        )
