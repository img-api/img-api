import re
import math
import time
import dateutil

from api.print_helper import *
from imgapi_launcher import db

from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

from datetime import datetime
from flask import abort, request

from flask_login import current_user
from werkzeug.exceptions import BadRequest


def get_adaptive_value(key, value):
    # Just check if true or false and change accordingly
    if key.find("date") != -1:
        print_h1(" DATE " + key)
        date_t = get_timestamp_verbose(value)
        ds = datetime.fromtimestamp(int(date_t))
        return ds

    if value == "true":
        return True
    elif value == "false":
        return False

    return value


class DB_DateTimeFieldTimestamp(db.DateTimeField):

    def to_mongo(self, value):
        if isinstance(value, int):
            value = datetime.fromtimestamp(int(value))

        return super().to_mongo(value)

    def to_python(self, value):
        if isinstance(value, int):
            value = datetime.fromtimestamp(int(value))

        return super().to_python(value)


def get_timestamp():
    d = datetime.now()
    unixtime = time.mktime(d.timetuple())
    return int(unixtime)


def date_from_unix(string):
    """Convert a unix timestamp into a utc datetime"""
    return datetime.utcfromtimestamp(float(string))


def date_to_unix(dt):
    """Converts a datetime object to unixtime"""
    unixtime = time.mktime(d.timetuple())
    return int(unixtime)


def timestamp_get_verbose_date(mytime):
    now = datetime.datetime.now()
    diff = (now - mytime).seconds
    if diff < 0:
        return "now"

    d = int(diff / (60 * 60 * 24))
    if d <= 15:
        if d == 1:
            return "1 day ago"

        if d > 1:
            return "%d days ago" % d

        h = int(diff / (60 * 60))
        m = int(diff / 60)

        if h == 1:
            return "1 hour ago"

        if h > 1:
            return "%d hours ago" % h

        if m < 5:
            return "a moment ago"

        if m == 0:
            return "now"

        return "%d minutes ago" % m

    return mytime


def month_string_to_number(string):
    m = {
        'jan': 1,
        'feb': 2,
        'mar': 3,
        'apr': 4,
        'may': 5,
        'jun': 6,
        'jul': 7,
        'aug': 8,
        'sep': 9,
        'oct': 10,
        'nov': 11,
        'dec': 12
    }

    s = string.strip()[:3].lower()
    try:
        return m[s]
    except:
        raise ValueError('Not a month')


def get_datetime_from_text(str):
    try:
        return dateutil.parser.parse(str)
    except Exception as e:
        print_exception(e, "DATEUTIL")

    return str


def get_timestamp_verbose(str):
    if not str:
        return get_timestamp()

    if isinstance(str, datetime):
        return int(str.timestamp())

    try:
        return int(str)
    except ValueError:
        pass

    if not 'hour' in str:
        try:
            return dateutil.parser.parse(str)
        except Exception as e:
            pass
            #print_exception(e, "DATEUTIL")

    try:
        month = month_string_to_number(str)
        d = datetime.now()
        return get_timestamp(d.replace(day=1, month=month))
    except ValueError:
        pass

    now = get_timestamp()
    if str == "now":
        return now

    if str == "month":
        return now - 31 * 24 * 60 * 60

    regex = re.compile(r"(\d+) year")
    year = regex.search(str)
    if year:
        return now - 365 * 24 * 60 * 60 * int(year.group(1))

    regex = re.compile(r"(\d+) month")
    months = regex.search(str)
    if months:
        return now - 31 * 24 * 60 * 60 * int(months.group(1))

    if str == "week":
        return now - 7 * 24 * 60 * 60

    regex = re.compile(r"(\d+) week")
    weeks = regex.search(str)
    if weeks:
        return now - 7 * 24 * 60 * 60 * int(weeks.group(1))

    if str == "day":
        return now - 24 * 60 * 60

    regex = re.compile(r"(\d+) day")
    days = regex.search(str)
    if days:
        return now - 24 * 60 * 60 * int(days.group(1))

    if str == "hour":
        return now - 60 * 60

    regex = re.compile(r"(\d+) hour?")
    hours = regex.search(str)
    if hours:
        return now - 60 * 60 * int(hours.group(1))

    if str == "minute":
        return now - 60

    regex = re.compile(r"(\d+) min")
    mins = regex.search(str)
    if mins:
        return now - 60 * int(mins.group(1))

    print("Didn't understand " + str)
    return now


def get_value_from_text(value):
    if value is bool:
        return value

    if value is int:
        return value >= 1

    value = str(value).strip().lower()
    if value in ['', 'none', 'null', 'undefined']:
        return None

    if value in ['1', 'true']:
        return True

    if value in ['0', 'false']:
        return False

    return value


def get_value_type_helper(obj, key, value):
    if key not in obj:
        if isinstance(value, bool) or isinstance(value, int) or isinstance(value, float):
            return value

        return str(value)

    field = obj[key]

    if isinstance(field, db.DateTimeField) or isinstance(field, datetime):
        # We round up to a second our timestamps.
        try:
            if isinstance(value, datetime):
                return value

            return datetime.fromtimestamp(int(float(value)))
        except Exception as e:
            print_exception(e, "CRASHED")
            return None

    if isinstance(field, bool) or isinstance(field, db.BooleanField):
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            value = value.lower()
            return (value in ['1', 'true'])

        if isinstance(value, int):
            return (value >= 1)

        return False

    if isinstance(field, float) or isinstance(field, db.FloatField):
        return float(value)

    if isinstance(field, int) or isinstance(field, db.IntField) or isinstance(field, db.LongField):
        return int(value)

    if isinstance(field, list) or isinstance(field, db.ListField):
        if isinstance(value, list):
            return value

        print_r(" List not implemeted properly yet ")
        return [value]

    if isinstance(field, datetime):
        return value

    if isinstance(field, str):
        value = value.strip()
        return value

    return value


def mongo_get_value(return_data, field, field_name, data, filter_out, add_empty_lists):
    """ Serialize a mongoengine object into a regular dict """

    if data is None:
        return

    if filter_out and field_name in filter_out:
        return

    if isinstance(field, db.ObjectIdField):
        return_data[field_name] = str(data)

    elif isinstance(field, db.EmbeddedDocumentField):
        return_data[field_name] = mongo_to_dict_helper(data, filter_out, add_empty_lists)

    elif isinstance(field, db.EmbeddedDocumentListField):
        if not add_empty_lists and len(data) == 0:
            return

        mylist = []
        for entry in data:
            mylist.append(mongo_to_dict_helper(entry, filter_out, add_empty_lists))
        return_data[field_name] = mylist

    elif isinstance(field, db.StringField):
        return_data[field_name] = str(data)
    elif isinstance(field, db.FloatField):
        if math.isnan(data):
            return_data[field_name] = 0
        else:
            return_data[field_name] = float(data)

    elif isinstance(field, db.BooleanField):
        if data:
            return_data[field_name] = True
        else:
            return_data[field_name] = False

    elif isinstance(field, db.IntField) or isinstance(field, db.LongField):
        try:
            if isinstance(data, datetime):
                return_data[field_name] = datetime.timestamp(data)
            elif math.isnan(data):
                return_data[field_name] = None
            else:
                return_data[field_name] = data
        except Exception as e:
            print_exception(e, "FAILED")
            pass

    elif isinstance(field, db.ListField):
        if not add_empty_lists and len(data) == 0:
            return

        mylist = []
        for entry in data:
            if isinstance(entry, db.DynamicEmbeddedDocument):
                mylist.append(mongo_to_dict_helper(entry, filter_out, add_empty_lists))
            else:
                mylist.append(clean_dict(field_name, entry))

        return_data[field_name] = mylist
    elif isinstance(field, db.DateTimeField):
        try:
            return_data[field_name] = datetime.timestamp(data)
        except Exception as e:
            pass

    else:
        print("+ Ignored " + field_name)
        # You can define your logic for returning elements

    return return_data


def clean_dict(mykey, obj):
    """ We get a dict that contains either a weak reference of another dict and we clean
        The extra information that makes json encoder to fail.
    """

    ret = {}
    try:
        from bson.objectid import ObjectId

        if isinstance(obj, str):
            return obj

        if isinstance(obj, ObjectId):
            return str(obj)

        if "__dict__" in obj:
            for key_, value_ in obj.__dict__.items():
                print_y(mykey + ":: " + key_)

                if value_ is None:
                    print_r(key_ + " is None")
                    continue

                try:
                    print_y(mykey + ":: " + key_ + " " + str(type(value_)))
                    if key_ == "_instance" and str(type(value_)) == "<class 'weakproxy'>":
                        print(obj._name)
                        return obj

                except Exception as err:
                    print_e(" EXCEPTION " + str(err))

                if key_[0:1] == "_":
                    print_y("PASS! " + key_)
                    continue

                ret[key_] = value_

        if ("_fields" in obj):
            return ret

        return obj

    except Exception as e:
        print_exception(e, ' CLEAN CRACK ')
    return ret


def has_iterator(obj):
    if hasattr(obj,
               '_result_cache'):  # Not sure why do I have to check this, on previous versions the iterator was enough.
        return True

    if (hasattr(obj, '__iter__') and hasattr(obj, 'next') and  # or __next__ in Python 3
            callable(obj.__iter__) and obj.__iter__() is obj):
        return True

    return False


def mongo_to_dict_helper(obj, filter_out=None, add_empty_lists=True):
    """ mongo object into a dictionary and lets you filter out fields you would like to not send to the next stage """

    if has_iterator(obj):
        ret = []
        for o in obj:
            ret.append(mongo_to_dict_helper(o, filter_out, add_empty_lists))
        return ret

    return_data = {}

    if isinstance(obj, bool) or isinstance(obj, str) or isinstance(obj, float) or isinstance(obj, int):
        return obj

    if not obj:
        print_alert("mongo_to_dict_helper - No data to return ")
        return return_data

    try:
        if isinstance(obj, dict):
            ret = {}
            for k, v in obj.items():
                ret[k] = mongo_to_dict_helper(v)
            return ret

        if hasattr(obj, '__dict__'):
            for key_, value in obj.__dict__.items():
                if key_[0:1] == "_":
                    continue

                if filter_out and key_ in filter_out:
                    continue

                if isinstance(value, dict):
                    return_data[key_] = clean_dict(key_, value)
                else:
                    return_data[key_] = value

                    try:
                        if math.isnan(value):
                            return_data[key_] = 0
                    except:
                        pass

            #return return_data

        if not hasattr(obj, '_fields') or "_fields" not in obj:
            return return_data

        for field_name in obj._fields:
            if filter_out and field_name in filter_out:
                continue

            if field_name[0:1] == "_":
                print("Ignore field " + field_name)
                continue

            if field_name in obj._data:
                data = obj._data[field_name]
                field = obj._fields[field_name]
                if field_name == "start_date":
                    print(" TEST ")

                mongo_get_value(return_data, field, field_name, data, filter_out, add_empty_lists)

    except Exception as e:
        print_exception(e, "Damage control")

    return return_data


def query_clean_reserved(args):
    args.pop('fields', None)
    args.pop('key', None)
    args.pop('k', None)
    args.pop('value', None)
    args.pop('database', None)
    args.pop('populate', None)
    args.pop('username', None)
    args.pop('order_by', None)
    return args


def build_query_from_request(MyClass, args=None, get_all=False, global_api=False):
    """ Global API means that the data doesn't belong to a particular user """

    order_by = None

    if not args:
        fields = request.args.get("fields", None)
        get_all = request.args.get("get_all")
        order_by = request.args.get("order_by")
        args = query_clean_reserved(request.args.to_dict())
    else:
        fields = args.get("fields", None)
        get_all = args.get("get_all")
        order_by = args.get("order_by")
        args = query_clean_reserved(args)

    query_set = QuerySet(MyClass, MyClass()._get_collection())

    for key, value in args.items():
        print(key, ":", value)

    # Limit the query to only some fields using projection
    if fields:
        projection = {field: 1 for field in fields.split(",")}
        query_set = query_set.only(*projection)

    # Admin can do whatever here
    if get_all and current_user.username == "admin":
        # print_b("Query All")
        data = query_set.all()
    else:
        if (len(args) > 5 or len(args) == 0):
            return abort(400, 'Range too wide or narrow')

        query = build_query_from_url(args)

        if not global_api:
            if not current_user.is_authenticated:
                query = Q(is_public=True) & query
            else:
                query = (Q(username=current_user.username) | Q(is_public=True)) & query

        data = query_set.filter(query)

    if data and order_by:
        data = data.order_by(order_by)

    if not data:
        print_r("Data not found")

    return data


def build_query_from_url(args=None):
    """
        This function converts the URL into a valid mongoengine/mongo format.

        We support a list functions __nin, __in and __all usign comma separated values
        example:
            /api_v1/events/get?state__nin=CLOSED,DELIVERED,PRODUCTION

        We convert true and false into native functions
        example:
            /api_v1/events/get?is_manual=true

        We support dates in timestamp or "verbose format". For example
        example:
            /api_v1/events/get?creation_date=30 days

    """
    if not args:
        args = request.args.to_dict()

    args = query_clean_reserved(args)

    clean_args = {}
    q_and = []
    q_or = []

    # Duplicated arguments are OR
    arguments = request.args.to_dict(flat=False)

    # First we find unique arguments.
    query = None
    for key, value in args.items():
        print(key, ":", value)
        if key[0] == "_":
            continue

        if "_date" in key:
            value = get_timestamp_verbose(value)
            newkey = {key: datetime.fromtimestamp(value)}
            myq = Q(**newkey)
            query = query & myq if query else myq
            continue

        if key in ["key", "database", "value", "k"]:
            print(" Rerverved words ")
            continue

        x = key.split("--")
        if len(x) > 1:
            newkey = {x[1]: value}
            if x[0] == "and":
                query = query & Q(**newkey) if query else Q(**newkey)

            elif x[0] == "or":
                query = query | Q(**newkey) if query else Q(**newkey)

        else:
            if value == "NULL":
                value = None

            if len(arguments[key]) > 1:
                query_or = None
                for v in arguments[key]:
                    newkey = {key: get_adaptive_value(key, v)}
                    query_or = query_or | Q(**newkey) if query_or else Q(**newkey)

                query = query & query_or if query else query_or
            else:

                parms = key.split("__")
                if len(parms) > 1:
                    if parms[1] in ['in', 'nin', 'all']:
                        value = value.split(",")

                newkey = {key: get_adaptive_value(key, value)}
                query = query & Q(**newkey) if query else Q(**newkey)

    return query


def mongo_to_dict_result(objects, filter_out=None, add_empty_lists=True):
    """ Converts a list of mongo objects and creates a valid dictionary,
        and filters out fields you are not interested on passing on to the next stage """
    ret = []
    try:

        for obj in objects:
            rdict = mongo_to_dict_helper(obj, filter_out, add_empty_lists)
            ret.append(rdict)

    except Exception as e:
        print_exception(e, "FAIL")

    return ret