from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.auditlog.models import SystemLog
from apps.catalog.models import CustomFieldDefinition, LaborRole, Machine, Material
from apps.core.models import AppSetting, Plant
from apps.imports_excel.models import ImportJob
from apps.imports_excel.services import generate_template_workbook
from apps.quotes.models import Customer, Quote, QuoteLine, QuoteLineParameterValue
from apps.templates_engine.models import (
    ProductFamily,
    ProductTemplate,
    TemplateBomItem,
    TemplateCostElement,
    TemplateFormula,
    TemplateMarginRule,
    TemplateOperation,
    TemplateParameter,
)


class Command(BaseCommand):
    help = "Seed demo users, plant, masters, Sheet Metal Box template, draft quote, sample Excel files"

    def handle(self, *args, **options):
        User = get_user_model()

        admin, created = User.objects.get_or_create(
            username="admin@example.com",
            defaults={
                "email": "admin@example.com",
                "role": User.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created or not admin.check_password("Admin123!"):
            admin.set_password("Admin123!")
            admin.role = User.Role.ADMIN
            admin.is_staff = True
            admin.is_superuser = True
            admin.save()

        quoter, created = User.objects.get_or_create(
            username="quoter@example.com",
            defaults={
                "email": "quoter@example.com",
                "role": User.Role.QUOTER,
            },
        )
        if created or not quoter.check_password("Quoter123!"):
            quoter.set_password("Quoter123!")
            quoter.role = User.Role.QUOTER
            quoter.save()

        plant, _ = Plant.objects.get_or_create(
            code="MAIN",
            defaults={"name": "Main Plant", "currency": "INR", "timezone": "Asia/Kolkata"},
        )
        AppSetting.objects.update_or_create(
            key="tour_enabled",
            defaults={"value": "true", "description": "Enable first-run product tour"},
        )

        CustomFieldDefinition.objects.get_or_create(
            plant=None,
            entity_type=CustomFieldDefinition.EntityType.MATERIAL,
            key="supplier",
            defaults={
                "label": "Supplier",
                "data_type": CustomFieldDefinition.DataType.TEXT,
                "is_importable": True,
                "import_column_header": "supplier",
                "sort_order": 10,
                "is_active": True,
            },
        )

        ms, _ = Material.objects.update_or_create(
            plant=plant,
            code="MS-SHEET",
            defaults={
                "name": "Mild Steel Sheet",
                "uom": "kg",
                "density": 7.85,
                "category": "Metal",
                "unit_price": 65,
                "currency": "INR",
                "is_active": True,
            },
        )
        Material.objects.update_or_create(
            plant=plant,
            code="AL-SHEET",
            defaults={
                "name": "Aluminium Sheet",
                "uom": "kg",
                "density": 2.7,
                "category": "Metal",
                "unit_price": 280,
                "currency": "INR",
                "is_active": True,
            },
        )

        laser, _ = Machine.objects.update_or_create(
            plant=plant,
            code="LASER-1",
            defaults={
                "name": "Fiber Laser Cutter",
                "hourly_rate": 1200,
                "setup_rate": 500,
                "efficiency_percent": 90,
                "is_active": True,
            },
        )
        Machine.objects.update_or_create(
            plant=plant,
            code="BEND-1",
            defaults={
                "name": "Press Brake",
                "hourly_rate": 800,
                "setup_rate": 300,
                "efficiency_percent": 95,
                "is_active": True,
            },
        )

        operator, _ = LaborRole.objects.update_or_create(
            plant=plant,
            code="OPERATOR",
            defaults={"name": "Machine Operator", "hourly_rate": 250, "is_active": True},
        )
        LaborRole.objects.update_or_create(
            plant=plant,
            code="WELDER",
            defaults={"name": "Welder", "hourly_rate": 320, "is_active": True},
        )

        family, _ = ProductFamily.objects.get_or_create(
            code="SHEET-METAL",
            defaults={"name": "Sheet Metal", "description": "Fabricated sheet metal products"},
        )

        tmpl, created = ProductTemplate.objects.get_or_create(
            plant=plant,
            code="SHEET-BOX",
            version=1,
            defaults={
                "family": family,
                "name": "Sheet Metal Box",
                "status": ProductTemplate.Status.PUBLISHED,
            },
        )
        if not created:
            tmpl.status = ProductTemplate.Status.PUBLISHED
            tmpl.family = family
            tmpl.name = "Sheet Metal Box"
            tmpl.save()

        params = [
            ("LENGTH", "Length", "mm", "500"),
            ("WIDTH", "Width", "mm", "300"),
            ("HEIGHT", "Height", "mm", "200"),
            ("THICKNESS", "Thickness", "mm", "2"),
        ]
        for i, (code, label, unit, default) in enumerate(params):
            TemplateParameter.objects.update_or_create(
                template=tmpl,
                code=code,
                defaults={
                    "label": label,
                    "data_type": "number",
                    "unit": unit,
                    "default_value": default,
                    "is_required": True,
                    "sort_order": i,
                },
            )

        TemplateFormula.objects.update_or_create(
            template=tmpl,
            code="VOLUME",
            defaults={
                "expression": "LENGTH * WIDTH * HEIGHT",
                "return_unit": "mm3",
                "description": "Internal volume",
                "sort_order": 1,
            },
        )
        TemplateFormula.objects.update_or_create(
            template=tmpl,
            code="SURFACE",
            defaults={
                "expression": "2 * (LENGTH * WIDTH + LENGTH * HEIGHT + WIDTH * HEIGHT)",
                "return_unit": "mm2",
                "description": "Outer surface area",
                "sort_order": 2,
            },
        )

        # qty in kg: surface_mm2 * thickness_mm * density_g_cm3 / 1e6
        TemplateBomItem.objects.update_or_create(
            template=tmpl,
            name="Body sheet",
            defaults={
                "material": ms,
                "qty_formula": "SURFACE * THICKNESS * DENSITY / 1000000",
                "scrap_formula": "0.05",
                "cost_group": "MATERIAL",
                "sort_order": 1,
            },
        )

        TemplateOperation.objects.update_or_create(
            template=tmpl,
            sequence=10,
            name="Laser Cut",
            defaults={
                "machine": laser,
                "labor_role": operator,
                "setup_time_formula_min": "15",
                "cycle_time_formula_min": "SURFACE / 50000",
                "labor_time_formula_min": "SURFACE / 50000",
                "notes": "Cutting time proportional to surface",
            },
        )

        TemplateCostElement.objects.update_or_create(
            template=tmpl,
            code="OVERHEAD",
            defaults={
                "name": "Shop overhead",
                "category": "OVERHEAD",
                "amount_formula": "0.1 * (TOTAL_MATERIAL + TOTAL_MACHINE + TOTAL_LABOR)",
            },
        )

        TemplateMarginRule.objects.update_or_create(
            template=tmpl,
            defaults={"method": "MARGIN_PERCENT", "value_or_formula": "25"},
        )

        customer = Customer.objects.filter(email="buyer@acme.example").order_by("id").first()
        if not customer:
            customer = Customer.objects.filter(code="CLI-ACME").first()
        if customer:
            # Merge any duplicate CLI-ACME row created by an earlier seed pass
            for dup in Customer.objects.filter(code="CLI-ACME").exclude(pk=customer.pk):
                Quote.objects.filter(customer=dup).update(customer=customer)
                dup.delete()
            customer.code = "CLI-ACME"
            customer.name = "Priya Sharma"
            customer.email = "buyer@acme.example"
            customer.phone = "+91 98765 43210"
            customer.company = "Acme Industrial"
            customer.gstin = "27AAAAA0000A1Z5"
            customer.address_line1 = "12 Industrial Estate"
            customer.city = "Pune"
            customer.state = "MH"
            customer.postal_code = "411001"
            customer.country = "India"
            customer.is_active = True
            customer.save()
        else:
            customer = Customer.objects.create(
                code="CLI-ACME",
                name="Priya Sharma",
                email="buyer@acme.example",
                phone="+91 98765 43210",
                company="Acme Industrial",
                gstin="27AAAAA0000A1Z5",
                address_line1="12 Industrial Estate",
                city="Pune",
                state="MH",
                postal_code="411001",
                country="India",
                is_active=True,
            )

        quote, _ = Quote.objects.get_or_create(
            number="Q-DEMO-001",
            defaults={
                "version": 1,
                "status": Quote.Status.DRAFT,
                "plant": plant,
                "customer": customer,
                "currency": "INR",
                "valid_until": timezone.now().date() + timedelta(days=30),
                "notes": "Demo quote ready to calculate",
                "created_by": admin,
            },
        )
        line, _ = QuoteLine.objects.get_or_create(
            quote=quote,
            template=tmpl,
            defaults={"description": "Sheet Metal Box", "quantity": 10, "sort_order": 1},
        )
        for code, _, _, default in params:
            QuoteLineParameterValue.objects.update_or_create(
                line=line, parameter_code=code, defaults={"value": default}
            )

        SystemLog.objects.get_or_create(
            source="seed_demo",
            event_type="OTHER",
            message="Demo environment seeded successfully",
            defaults={"level": "INFO", "context": {"plant": "MAIN"}},
        )
        SystemLog.objects.get_or_create(
            source="seed_demo",
            event_type="OTHER",
            message="Reminder: search Error Logs by correlation id from flash messages",
            defaults={"level": "INFO", "context": {}},
        )

        # Blank + sample Excel files
        samples = Path(settings.EXCEL_TEMPLATES_DIR) / "samples"
        samples.mkdir(parents=True, exist_ok=True)
        blank_dir = Path(settings.EXCEL_TEMPLATES_DIR)
        blank_dir.mkdir(parents=True, exist_ok=True)

        mapping = {
            ImportJob.EntityType.MATERIAL: "materials_template.xlsx",
            ImportJob.EntityType.MACHINE: "machines_template.xlsx",
            ImportJob.EntityType.LABOR: "labor_template.xlsx",
            ImportJob.EntityType.QUOTE_INPUT: "quote_inputs_template.xlsx",
        }
        for et, name in mapping.items():
            data = generate_template_workbook(et)
            (blank_dir / name).write_bytes(data)
            (samples / name.replace("_template", "_sample")).write_bytes(data)

        # Richer materials sample with two rows
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Data"
        ws.append(
            [
                "plant_code",
                "code",
                "name",
                "uom",
                "density",
                "category",
                "unit_price",
                "currency",
                "effective_from",
                "effective_to",
                "is_active",
                "supplier",
            ]
        )
        ws.append(
            ["MAIN", "MS-SHEET", "Mild Steel Sheet", "kg", 7.85, "Metal", 65, "INR", "2024-01-01", "", "TRUE", "Tata"]
        )
        ws.append(
            ["MAIN", "SS-304", "Stainless 304 Sheet", "kg", 8.0, "Metal", 220, "INR", "2024-01-01", "", "TRUE", "Jindal"]
        )
        instr = wb.create_sheet("INSTRUCTIONS")
        instr.append(["Sample filled materials file for demo import"])
        sample_path = samples / "materials_sample.xlsx"
        wb.save(sample_path)

        self.stdout.write(self.style.SUCCESS("Demo data seeded."))
        self.stdout.write("Admin: admin@example.com / Admin123!")
        self.stdout.write("Quoter: quoter@example.com / Quoter123!")
        self.stdout.write(f"Sample Excel: {sample_path}")
