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
    

# =========================================================
# CUSTOMER MODEL
# =========================================================

class Customer(models.Model):

    name = models.CharField(
        max_length=100
    )

    email = models.EmailField(
        max_length=150
    )

    phone = models.CharField(
        max_length=10
    )

    address = models.TextField()

    city = models.CharField(
        max_length=100
    )

    state = models.CharField(
        max_length=100
    )

    pincode = models.CharField(
        max_length=6
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

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

    name = models.CharField(
        max_length=150
    )

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    stock = models.PositiveIntegerField(
        default=0
    )

    gst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    description = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Product"
        verbose_name_plural = "Products"