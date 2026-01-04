from rest_framework.exceptions import APIException
from rest_framework import status


class SlotAlreadyBooked(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This slot is already booked"
