from django.db import models
from django.contrib.auth.models import User


class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.otp}"


class DistributorProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="distributor_profile"
    )
    phone = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Customer(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=150)
    phone = models.CharField(max_length=10)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Customer"
        verbose_name_plural = "Customers"


class Product(models.Model):

    CATEGORY_CHOICES = [
        ("Electronics", "Electronics"),
        ("Grocery", "Grocery"),
        ("Clothing", "Clothing"),
        ("Furniture", "Furniture"),
        ("Stationery", "Stationery"),
        ("Medicine", "Medicine"),
        ("Food", "Food"),
        ("Other", "Other"),
    ]

    name = models.CharField(max_length=150)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Product"
        verbose_name_plural = "Products"


# ==========================================================
# INVOICE MODEL
# ==========================================================

class Invoice(models.Model):

    PAYMENT_STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Paid", "Paid"),
        ("Cancelled", "Cancelled"),
    ]

    invoice_number = models.CharField(
        max_length=30,
        unique=True
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="invoices"
    )

    invoice_date = models.DateTimeField(
        auto_now_add=True
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    gst_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    grand_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="Pending"
    )

    notes = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.invoice_number

    @property
    def customer_name(self):
        """Customer name dynamically retrieved from the related Customer model."""
        return self.customer.name if self.customer else "N/A"

    @property
    def total_bill(self):
        """Total bill amount dynamically retrieved from the Invoice model."""
        return self.grand_total

    @property
    def formatted_date(self):
        """Invoice date formatted dynamically from the Invoice model."""
        return self.invoice_date.strftime("%d %b %Y, %I:%M %p")

    @property
    def product_summary(self):
        """
        Product summary dynamically retrieved from related InvoiceItem models.
        e.g. 'watch (x1), laptop (x2)'
        """
        items = list(self.items.select_related("product").all()) if hasattr(self.items, "select_related") else list(self.items.all())
        if not items:
            return "No products"
        return ", ".join([f"{item.product.name} (x{item.quantity})" for item in items])

    @property
    def product_count(self):
        """Number of distinct line items / products in the invoice."""
        return self.items.count()

    @property
    def total_quantity(self):
        """Total unit quantity of products in the invoice."""
        return sum(item.quantity for item in self.items.all())

    def get_qr_data(self):
        """Generate structured text for QR code encoding."""
        from .utils import generate_invoice_qr_data
        return generate_invoice_qr_data(self)

    def generate_qr_base64(self):
        """Generate Base64 data URI of the invoice QR code."""
        from .utils import generate_invoice_qr_base64
        return generate_invoice_qr_base64(self)

    @property
    def qr_code_base64(self):
        """Dynamic Base64 data URI of the invoice QR code for templates and PDFs."""
        return self.generate_qr_base64()

    class Meta:
        ordering = ["-invoice_date"]
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"



# ==========================================================
# INVOICE ITEM MODEL
# ==========================================================

class InvoiceItem(models.Model):

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="invoice_items"
    )

    quantity = models.PositiveIntegerField(
        default=1
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    gst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    gst_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.product.name}"

    class Meta:
        verbose_name = "Invoice Item"
        verbose_name_plural = "Invoice Items"