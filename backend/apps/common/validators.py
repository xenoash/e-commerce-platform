from django.core.validators import RegexValidator

saudi_vat_number = RegexValidator(
    r"^3\d{13}3$", "A Saudi VAT number has 15 digits and starts and ends with 3.", "invalid_vat_number"
)
commercial_registration = RegexValidator(r"^\d{10}$", "A commercial registration number has 10 digits.", "invalid_cr")
building_number = RegexValidator(r"^\d{4}$", "A building number has 4 digits.", "invalid_building_number")
postal_code = RegexValidator(r"^\d{5}$", "A postal code has 5 digits.", "invalid_postal_code")
saudi_phone = RegexValidator(
    r"^\+9665\d{8}$", "Use the international format, for example +966512345678.", "invalid_phone"
)
