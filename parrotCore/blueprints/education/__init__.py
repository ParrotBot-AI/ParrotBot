from flask import Blueprint, request
from utils.response_tools import (SuccessDataResponse, ArgumentExceptionResponse)
import json
from utils.redis_tools import RedisWrapper
import uuid as u

bp = Blueprint('education_api', __name__, url_prefix='/o1/education/api')