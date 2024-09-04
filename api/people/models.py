from mongoengine import *
from api.print_helper import *
from api.query_helper import *


class DB_Position(EmbeddedDocument):
    """
    Represents a position held by a person in a company.
    """
    title = StringField(required=True)
    company_name = StringField(required=True)
    start_date = DateField()  # Optional field for start date
    end_date = DateField()  # Optional field for end date
    current = StringField(choices=["Yes", "No"], default="No")  # Indicates if this is a current position


class DB_People(DynamicDocument):
    """ An object, person, animal/model """
    meta = {
        'strict': False,
    }

    # Basic Information
    name = StringField(required=True)  # First name of the person
    middle_name = StringField()  # Optional middle name
    surname = StringField(required=True)  # Last name of the person
    full_name = StringField()  # Full name of the person, which can be auto-computed
    alternative_names = ListField(StringField(), default=list)  # Alternative names or aliases

    # Tags and Synonyms
    synonymous = ListField(StringField(), default=list)  # Synonyms or related names
    tags = ListField(StringField(), default=list)  # Tags related to the person (e.g., industry, role)

    # Contact Information
    emails = ListField(EmailField(), default=list)  # List of email addresses
    websites = ListField(URLField(), default=list)  # List of personal or professional websites
    phone_numbers = ListField(StringField(), default=list)  # List of phone numbers

    # Professional Information
    company_tickers = ListField(StringField(), default=list)  # Tickers of companies associated with the person
    positions = ListField(EmbeddedDocumentField(DB_Position), default=list)  # List of positions held by the person

    # Personal Information
    birth_year = IntField()  # Birth year, if known
    nationality = StringField()  # Nationality of the person
    education = ListField(StringField(), default=list)  # List of educational qualifications

    # Social Media and Other Links
    social_media_profiles = ListField(URLField(), default=list)  # Links to social media profiles

    # Miscellaneous
    notes = StringField()  # Additional notes or comments about the person
