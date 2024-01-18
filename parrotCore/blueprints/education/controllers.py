from blueprints.education.models import (
    Exams,
    Subjects,
    Patterns,
    Sections,
    Resources,
    QuestionsType,
    IndicatorQuestion,
    Indicators,
    Questions,
)
from configs.environment import DATABASE_SELECTION

if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import get_db_session as db_session
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import get_db_session_sql as db_session

from utils import abspath
from utils.logger_tools import get_general_logger
from blueprints.util.crud import crudController
from blueprints.util.serializer import Serializer as s

logger = get_general_logger('account', path=abspath('logs', 'core_web'))


class TransactionsController(crudController):
    """
    事务模块 继承crudController
    调用CRUD: _create; _retrieve; _update; _delete
    支持所有事务表单(Exams, Sections, Patterns, Resources)
    init: 先创建Exams => Patterns => Sections, Resources
    """

    def _get_all_exams(self, active=None):
        with db_session('core') as session:
            if active:
                exams = (
                    session.query(Exams)
                    .filter(Exams.is_active == active)
                    .all()
                )
                return s.serialize_list(exams, self.default_not_show)
            else:
                exams = (
                    session.query(Exams)
                    .all()
                )
                return s.serialize_list(exams, self.default_not_show)

    def _get_all_patterns_under_exam(self, exam_id, active=None):
        with db_session('core') as session:
            exam = self._retrieve(model=Exams, restrict_field='id', restrict_value=exam_id)
            if exam:
                if active:
                    patterns = (
                        session.query(Patterns)
                        .filter(Patterns.exam_id == exam_id)
                        .filter(Patterns.is_active == active)
                        .all()
                    )
                    return s.serialize_list(patterns, self.default_not_show)
                else:
                    patterns = (
                        session.query(Patterns)
                        .filter(Patterns.exam_id == exam_id)
                        .all()
                    )
                    return s.serialize_list(patterns, self.default_not_show)
            else:
                return 'Invalid Exam Id'

    def _get_all_sections_under_pattern(self, pattern_id, active=None):
        with db_session('core') as session:
            pattern = self._retrieve(model=Patterns, restrict_field='id', restrict_value=pattern_id)
            if pattern:
                if active:
                    sections = (
                        session.query(Sections)
                        .filter(Sections.pattern_id == pattern_id)
                        .filter(Sections.is_active == active)
                        .all()
                    )
                    return s.serialize_list(sections, self.default_not_show)
                else:
                    sections = (
                        session.query(Sections)
                        .filter(Sections.pattern_id == pattern_id)
                        .all()
                    )
                    return s.serialize_list(sections, self.default_not_show)

            else:
                return 'Invalid Pattern Id'


class QuestionsController(crudController):
    """
    问题 继承crudController
    调用CRUD: _create; _retrieve; _update; _delete
    支持所有问题相关表单(Questions, QuestionsType, Indicators, IndicatorQuestion)
    init: 先定义Indicators, QuestionsType => Questions => IndicatorQuestion
    """

    def _get_all_questions_under_section(self, section_id, active=None):
        with db_session('core') as session:
            section = self._retrieve(model=Sections, restrict_field='id', restrict_value=section_id)
            if section:
                if active:
                    questions = (
                        session.query(Questions)
                        .filter(Questions.section_id == section_id)
                        .all()
                    )
                    return s.serialize_list(questions, self.default_not_show)
                else:
                    questions = (
                        session.query(Questions)
                        .filter(Questions.section_id == section_id)
                        .filter(Questions.is_active == active)
                        .all()
                    )
                    return s.serialize_list(questions, self.default_not_show)
            else:
                return 'Invalid Section Id'


if __name__ == '__main__':
    #
    init = TransactionsController()
    exam = {
        'exam_name': "托福",
        'exam_eng_name': "TOEFL",
        'no_patterns': 4,
        'duration': 120,
        'max_score': 120,
    }
    # exam_db = init._retrieve(model=Exams, restrict_field='exam_name', restrict_value='托福')
    # _id = exam_db.id
    # Pattern = [
    #     {
    #         'exam_id': _id,
    #         'pattern_name': '阅读',
    #         'pattern_eng_name': 'Reading',
    #         'duration': 35,
    #         'max_score': 30
    #     },
    #     {
    #         'exam_id': _id,
    #         'pattern_name': '听力',
    #         'pattern_eng_name': 'Listening',
    #         'duration': 36,
    #         'max_score': 30
    #     },
    #     {
    #         'exam_id': _id,
    #         'pattern_name': '口语',
    #         'pattern_eng_name': 'Speaking',
    #         'duration': 17,
    #         'max_score': 30
    #     },
    #     {
    #         'exam_id': _id,
    #         'pattern_name': '写作',
    #         'pattern_eng_name': 'writing',
    #         'duration': 29,
    #         'max_score': 30
    #     }
    # ]
    # for item in Pattern:
    #     record = init._create(model=Patterns, create_params=item)
    #     if record == True:
    #         print("Success add!")
