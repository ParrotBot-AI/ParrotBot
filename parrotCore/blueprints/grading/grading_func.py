import numpy as np

class Grading:
    @staticmethod
    def grading_order(answer, correct, rubric, restriction, max_score, **kwargs):
        if answer == correct:
            return max_score
        else:
            return 0

    @staticmethod
    def grading_s_choice(answer, correct, weight, rubric, restriction, max_score):
        result = np.dot(np.array(answer), np.array(weight).T)
        score = result * max_score
        return score

    @staticmethod
    def grading_m_choice(answer, correct, weight, rubric, restriction, max_score):
        def evaluate_conditions(sum_, rules):
            # Loop through each rule in the dictionary
            for condition, result in rules.items():
                if condition != "*":
                    operator, value = condition.split()
                    value = int(value)
                    # Evaluate the condition
                    if eval(f"sum_ {operator} {value}"):
                        return result

            # Default case if no conditions match
            return rules["*"]

        if restriction['r'] == 1 and sum(answer) != restriction['rc']:
            return 0

        # These lines are executed in both cases when the restriction is not met or when there's no restriction.
        sum_ = np.dot(np.array(answer), np.array(weight).T)
        result_ = evaluate_conditions(sum_, rubric)
        score = result_ * max_score
        return score

    @staticmethod
    def grading_speaking(sheet_id, question_id, **kwargs):
        from blueprints.education.controllers import AnsweringScoringController
        res, score = AnsweringScoringController().model_scoring(sheet_id=sheet_id, question_id=question_id)
        if res:
            return score
        else:
            return 0

    @staticmethod
    def grading_writing(sheet_id, question_id, **kwargs):
        from blueprints.education.controllers import AnsweringScoringController
        res, score = AnsweringScoringController().model_scoring(sheet_id=sheet_id, question_id=question_id)
        if res:
            return score
        else:
            return 0






if __name__ == "__main__":
    # Grading.grading_m_choice([1, 0, 0, 1, 1, 0], [1, 1, 1, 0, 0, 0], [1, 1, 1, 0, 0, 0], {"== 3":1, "== 2":0.5, "*":0}, 3, 2)
    pass