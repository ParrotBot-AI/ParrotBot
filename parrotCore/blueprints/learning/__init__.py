from flask import Blueprint, request
from utils.response_tools import (SuccessDataResponse, ArgumentExceptionResponse)
import json
from utils.redis_tools import RedisWrapper
import uuid as u

bp = Blueprint('learning_api', __name__, url_prefix='/v1/api/learning/')