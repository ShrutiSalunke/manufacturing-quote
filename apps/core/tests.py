import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.auditlog.models import SystemLog
from apps.catalog.models import CustomFieldDefinition, Material
from apps.core.logging_utils import log_event
from apps.core.models import Plant
from apps.costing.engine import FormulaError
from apps.costing.services import calculate_quote, cost_template
from apps.imports_excel.models import ImportJob
from apps.imports_excel.services import generate_template_workbook, import_workbook
from apps.onboarding.models import UserTourState
from apps.quotes.models import Quote, QuoteDocument
from apps.quotes.pdf import generate_quote_pdf
from apps.templates_engine.models import ProductTemplate, TemplateFormula


User = get_user_model()


class ManufacturingQuoteMVPTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Use seed command for rich fixtures
        from django.core.management import call_command

        call_command("seed_demo")

    def setUp(self):
        self.admin = User.objects.get(username="admin@example.com")
        self.quoter = User.objects.get(username="quoter@example.com")
        self.client = Client()

    def test_admin_login(self):
        ok = self.client.login(username="admin@example.com", password="Admin123!")
        self.assertTrue(ok)
        resp = self.client.get(reverse("core:dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_materials_template_includes_custom_field(self):
        CustomFieldDefinition.objects.create(
            entity_type=CustomFieldDefinition.EntityType.MATERIAL,
            key="grade",
            label="Grade",
            data_type="text",
            is_importable=True,
            import_column_header="grade",
            is_active=True,
        )
        content = generate_template_workbook(ImportJob.EntityType.MATERIAL)
        from io import BytesIO

        from openpyxl import load_workbook

        wb = load_workbook(BytesIO(content))
        headers = [c.value for c in wb.active[1]]
        self.assertIn("grade", headers)
        self.assertIn("plant_code", headers)

    def test_import_sample_materials(self):
        sample = Path(settings.EXCEL_TEMPLATES_DIR) / "samples" / "materials_sample.xlsx"
        self.assertTrue(sample.exists())
        self.client.login(username="admin@example.com", password="Admin123!")
        with sample.open("rb") as fh:
            uploaded = SimpleUploadedFile(
                "materials_sample.xlsx",
                fh.read(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        job = ImportJob.objects.create(
            entity_type=ImportJob.EntityType.MATERIAL,
            uploaded_file=uploaded,
            created_by=self.admin,
        )
        import_workbook(job)
        self.assertGreaterEqual(job.row_success, 1)
        self.assertTrue(Material.objects.filter(code="SS-304").exists())

    def test_sheet_metal_box_calculator_nonzero(self):
        tmpl = ProductTemplate.objects.get(code="SHEET-BOX", version=1)
        result = cost_template(
            tmpl,
            {"LENGTH": 500, "WIDTH": 300, "HEIGHT": 200, "THICKNESS": 2},
            line_qty=10,
        )
        self.assertGreater(result["totals"]["material"], 0)
        self.assertGreater(result["totals"]["machine"], 0)
        self.assertGreater(result["totals"]["selling_price"], 0)

    def test_quote_calculate_and_pdf(self):
        quote = Quote.objects.get(number="Q-DEMO-001")
        data = calculate_quote(quote, user=self.admin)
        quote.refresh_from_db()
        self.assertEqual(quote.status, Quote.Status.CALCULATED)
        self.assertIn("totals", data)
        doc = generate_quote_pdf(quote, user=self.admin)
        self.assertTrue(doc.pdf_file)
        self.assertTrue(QuoteDocument.objects.filter(quote=quote).exists())
        self.assertGreater(doc.pdf_file.size, 100)

    def test_bad_formula_logs_to_systemlog_not_file(self):
        tmpl = ProductTemplate.objects.get(code="SHEET-BOX", version=1)
        TemplateFormula.objects.filter(template=tmpl, code="VOLUME").update(expression="LENGTH / 0")
        quote = Quote.objects.get(number="Q-DEMO-001")
        quote.status = Quote.Status.DRAFT
        quote.save()
        before = SystemLog.objects.filter(event_type="COSTING", level="ERROR").count()
        with self.assertRaises(FormulaError) as ctx:
            calculate_quote(quote, user=self.admin)
        self.assertTrue(getattr(ctx.exception, "correlation_id", None))
        after = SystemLog.objects.filter(event_type="COSTING", level="ERROR").count()
        self.assertGreater(after, before)
        quote.refresh_from_db()
        self.assertNotEqual(quote.status, Quote.Status.CALCULATED)
        # No error log file required / created by our config
        self.assertFalse((Path(settings.BASE_DIR) / "logs" / "app.log").exists())
        logging_config = settings.LOGGING
        handlers = logging_config.get("handlers", {})
        for name, conf in handlers.items():
            cls = conf.get("class", "")
            self.assertNotIn("FileHandler", cls)
            self.assertNotIn("RotatingFileHandler", cls)

    def test_unhandled_exception_writes_systemlog(self):
        from apps.core.middleware import ExceptionLoggingMiddleware
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/boom/")
        request.user = self.admin
        request.correlation_id = __import__("uuid").uuid4()
        mw = ExceptionLoggingMiddleware(lambda r: None)
        before = SystemLog.objects.filter(event_type="EXCEPTION").count()
        try:
            raise RuntimeError("forced boom")
        except RuntimeError as exc:
            result = mw.process_exception(request, exc)
        # Tests run with DEBUG=False → friendly 500 with correlation id
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 500)
        self.assertIn(str(request.correlation_id), result.content.decode())
        after = SystemLog.objects.filter(event_type="EXCEPTION").count()
        self.assertGreater(after, before)
        latest = SystemLog.objects.filter(event_type="EXCEPTION").order_by("-created_at").first()
        self.assertIn("forced boom", latest.message)
        self.assertTrue(latest.traceback)

    def test_exception_middleware_sets_correlation_header(self):
        self.client.login(username="admin@example.com", password="Admin123!")
        resp = self.client.get(reverse("core:dashboard"))
        self.assertIn("X-Correlation-Id", resp.headers)

    def test_tour_restart(self):
        self.client.login(username="admin@example.com", password="Admin123!")
        state, _ = UserTourState.objects.get_or_create(user=self.admin, tour_key="mvp_first_run")
        state.completed = True
        state.save()
        resp = self.client.get(reverse("onboarding:restart_tour"))
        self.assertEqual(resp.status_code, 302)
        state.refresh_from_db()
        self.assertFalse(state.completed)
        self.assertFalse(state.dismissed)

    def test_quoter_forbidden_from_admin_pages(self):
        self.client.login(username="quoter@example.com", password="Quoter123!")
        self.assertEqual(self.client.get(reverse("catalog:custom_field_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("auditlog:log_list")).status_code, 403)
        tmpl = ProductTemplate.objects.get(code="SHEET-BOX", version=1)
        self.assertEqual(self.client.get(reverse("templates_engine:template_edit", args=[tmpl.pk])).status_code, 403)

    def test_download_template_authenticated(self):
        self.client.login(username="admin@example.com", password="Admin123!")
        resp = self.client.get(reverse("imports_excel:download_template", args=["MATERIAL"]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            "spreadsheetml",
            resp["Content-Type"],
        )
