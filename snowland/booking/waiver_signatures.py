from .models import MemberWaiverSignature


SIGNATURE_WIDTH = 1000
SIGNATURE_HEIGHT = 400
SIGNATURE_MAX_POINTS = 3000


def validate_signature_strokes(strokes):
    if not isinstance(strokes, list) or not strokes or len(strokes) > 100:
        raise ValueError('請先在簽名板完成手寫簽名')
    points = 0
    has_ink = False
    for stroke in strokes:
        if not isinstance(stroke, list) or not stroke:
            raise ValueError('手寫簽名格式不正確')
        points += len(stroke)
        if points > SIGNATURE_MAX_POINTS:
            raise ValueError('手寫簽名筆畫過多，請清除後重簽')
        for point in stroke:
            if (
                not isinstance(point, list) or len(point) != 2
                or any(type(value) is not int for value in point)
                or not 0 <= point[0] <= SIGNATURE_WIDTH
                or not 0 <= point[1] <= SIGNATURE_HEIGHT
            ):
                raise ValueError('手寫簽名格式不正確')
            has_ink |= point != stroke[0]
    if not has_ink:
        raise ValueError('請先在簽名板完成手寫簽名')
    return strokes


def current_signature_strokes(members):
    signed = {
        (member.pk, member.waiver_completed_at): member.waiver_document_version
        for member in members if member.waiver_completed_at and member.waiver_signature
    }
    if not signed:
        return {}
    return {
        row.member_id: row.strokes
        for row in MemberWaiverSignature.objects.filter(
            member_id__in={key[0] for key in signed},
            signed_at__in={key[1] for key in signed},
        ).only('member_id', 'signed_at', 'document_version', 'strokes')
        if signed.get((row.member_id, row.signed_at)) == row.document_version
    }
