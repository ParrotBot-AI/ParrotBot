from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Enum, Text, Float
from configs.environment import DATABASE_SELECTION
import enum

if DATABASE_SELECTION == 'postgre':
    from configs.postgre_config import BASES
elif DATABASE_SELECTION == 'mysql':
    from configs.mysql_config import BASES


# ==================== Enums ====================#
class level(enum.Enum):
    middle_school = 1
    high_school = 2
    college = 3
    toefl = 4
    gre = 5
    grad = 6


class question_function(enum.Enum):
    exams = 1
    evaluation = 2
    learning = 3


# ==================== Tables ====================#
class Subjects(BASES['core']):
    __tablename__ = "Subjects"

    id = Column(Integer, autoincrement=True, primary_key=True)
    subject_name = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} n: {self.subject_name})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} n: {self.subject_name})'
        return s


class Exams(BASES['core']):
    __tablename__ = "Exams"

    id = Column(Integer, autoincrement=True, primary_key=True)
    exam_name = Column(String(20), nullable=False)
    exam_eng_name = Column(String(20), nullable=False)
    duration = Column(Float, nullable=True)
    max_score = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    is_current_use = Column(Boolean, default=True)
    # father_exam = Column(Integer, nullable=False, default=-1)
    no_patterns = Column(Integer, nullable=True)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} n: {self.exam_name} d: {self.duration} s:{self.max_score} p:{self.no_patterns})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} n: {self.exam_name} d: {self.duration} s:{self.max_score} p:{self.no_patterns})'
        return s


class Patterns(BASES['core']):
    __tablename__ = "Patterns"

    id = Column(Integer, autoincrement=True, primary_key=True)
    exam_id = Column(Integer, ForeignKey('Exams.id', ondelete='CASCADE'), nullable=False)
    pattern_name = Column(String(20), nullable=False)
    pattern_eng_name = Column(String(20), nullable=False)
    duration = Column(Float, nullable=True)
    max_score = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    no_sections = Column(Integer, nullable=True)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} n: {self.pattern_name} d: {self.duration} s:{self.max_score} p:{self.no_sections})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} n: {self.pattern_name} d: {self.duration} s:{self.max_score} p:{self.no_sections})'
        return s


class Sections(BASES['core']):
    __tablename__ = "Sections"

    id = Column(Integer, autoincrement=True, primary_key=True)
    pattern_id = Column(Integer, ForeignKey('Patterns.id', ondelete='CASCADE'), nullable=False)
    section_name = Column(String(20), nullable=False)
    section_eng_name = Column(String(20), nullable=False)
    duration = Column(Float, nullable=True)
    max_score = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    no_questions = Column(Integer, nullable=True)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} n: {self.section_name} d: {self.duration} s:{self.max_score} p:{self.no_questions})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} n: {self.section_name} d: {self.duration} s:{self.max_score} p:{self.no_questions})'
        return s


class Resources(BASES['core']):
    __tablename__ = "Resources"

    id = Column(Integer, autoincrement=True, primary_key=True)
    resource_name = Column(String(20), nullable=False)
    resource_eng_name = Column(String(20), nullable=False)
    father_resource = Column(Integer, nullable=False)
    section_id = Column(Integer, ForeignKey('Sections.id', ondelete='CASCADE'), nullable=True)
    pattern_id = Column(Integer, ForeignKey('Patterns.id', ondelete='CASCADE'), nullable=True)
    exam_id = Column(Integer, ForeignKey('Exams.id', ondelete='CASCADE'), nullable=False)
    is_active = Column(Boolean, default=True)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} n: {self.resource_name})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} n: {self.resource_name})'
        return s


class Indicators(BASES['core']):
    __tablename__ = "Indicators"

    id = Column(Integer, autoincrement=True, primary_key=True)
    indicator_name = Column(String(20), nullable=False)
    indicator_weight = Column(Integer, nullable=True)
    father_indicator = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} n: {self.indicator_name} w: {self.indicator_weight})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} n: {self.indicator_name} w: {self.indicator_weight})'
        return s


class QuestionsType(BASES['core']):
    __tablename__ = "QuestionsType"

    id = Column(Integer, autoincrement=True, primary_key=True)
    type_name = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True)
    rubric = Column(String(50), nullable=False)
    limitation = Column(String(50), nullable=True)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} n: {self.type_name})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} n: {self.type_name})'
        return s


class Questions(BASES['core']):
    __tablename__ = "Questions"
    # __table_args__ = (
    #     UniqueConstraint('question_title', ), {"extend_existing": True, 'mysql_charset': 'utf8', }
    # )

    id = Column(Integer, autoincrement=True, primary_key=True)
    question_type = Column(Integer, ForeignKey('QuestionsType.id', ondelete='CASCADE'), nullable=False)
    question_title = Column(String(20), nullable=False)
    question_content = Column(Text, nullable=False)
    question_stem = Column(String(600), nullable=False)
    question_function_type = Column(Enum(question_function), nullable=True)

    order = Column(Integer, nullable=True)  # 题目号
    father_question = Column(Integer, nullable=True)
    cal_method = Column(Integer, nullable=False)  # 计算方式
    duration = Column(Float, nullable=False)  # 做题时间
    max_score = Column(Integer, nullable=False)  # 题目最大分值
    stem_weights = Column(String(20), nullable=True)  # 题目stem权重
    correct_answer = Column(String(20), nullable=True)  # 题目的正确值
    rubric_detail = Column(String(50), nullable=True)
    d_level = Column(Integer, nullable=True)  # 题目难度
    voice_link = Column(String(20), nullable=True)  # Link to voice if it requires voice (听力题)
    is_require = Column(Boolean, default=True)  # 是否必答
    is_cal = Column(Boolean, default=True)  # 是否记分
    is_active = Column(Boolean, default=True)
    is_attachable = Column(Boolean, default=True)  # 是否可以上传文件
    keywords = Column(String(20), nullable=True)  # 题目关键词

    # foreign keys
    section_id = Column(Integer, ForeignKey('Sections.id', ondelete='CASCADE'), nullable=True)
    subject_id = Column(Integer, ForeignKey('Subjects.id', ondelete='CASCADE'), nullable=True)
    source = Column(Integer, ForeignKey('Resources.id', ondelete='CASCADE'), nullable=True)

    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} t: {self.question_title})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} t: {self.question_title})'
        return s


class IndicatorQuestion(BASES['core']):
    __tablename__ = "Indicators_Questions"

    id = Column(Integer, autoincrement=True, primary_key=True)
    indicator_id = Column(Integer, ForeignKey('Indicators.id', ondelete='CASCADE'), nullable=False)
    question_id = Column(Integer, ForeignKey('Questions.id', ondelete='CASCADE'), nullable=False)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} i: {self.indicator_id} q: {self.question_id})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} i: {self.indicator_id} q: {self.question_id})'
        return s


class Submissions(BASES['core']):
    __tablename__ = "Submissions"

    id = Column(Integer, autoincrement=True, primary_key=True)
    account_id = Column(Integer, ForeignKey('Accounts.id', ondelete='CASCADE'), nullable=False)
    question_id = Column(Integer, ForeignKey('Questions.id', ondelete='CASCADE'), nullable=False)
    answer = Column(Text, nullable=True)
    duration = Column(Float, nullable=False) # 做题时长
    voice_link = Column(String(20), nullable=True)
    video_link = Column(String(20), nullable=True)
    upload_file_link = Column(String(20), nullable=True)
    score = Column(Integer, nullable=True)
    graded = Column(Integer, nullable=False)  # 是否打分完成
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} a: {self.answer})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} a: {self.answer})'
        return s


class Analysis(BASES['core']):
    __tablename__ = "Analysis"

    id = Column(Integer, autoincrement=True, primary_key=True)
    question_id = Column(Integer, ForeignKey('Questions.id', ondelete='CASCADE'), nullable=False)
    analysis_text = Column(Text, nullable=True)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} a: {self.analysis_text[:15]})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} a: {self.analysis_text[:15]})'
        return s


class VocabBase(BASES['core']):
    __tablename__ = "Vocabs"

    id = Column(Integer, autoincrement=True, primary_key=True)
    word = Column(String(20), nullable=True)
    level = Column(Enum(level), nullable=True)
    create_time = Column(DateTime)
    last_update_time = Column(DateTime)

    def __str__(self) -> str:
        s = f'(id: {self.id} w: {self.word})'
        return s

    def __repr__(self) -> str:
        s = f'(id: {self.id} w: {self.word})'
        return s


if __name__ == "__main__":
    for BASE in BASES.values():
        BASE.metadata.create_all()