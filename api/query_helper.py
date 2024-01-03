import math

from api.print_helper import *
from imgapi_launcher import db

from datetime import datetime


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

        if ("_fields" not in obj):
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
                mongo_get_value(return_data, field, field_name, data, filter_out, add_empty_lists)

    except Exception as e:
        print_exception(e, "Damage control")

    return return_data


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