from app.models import User, Cafe, Reservation, Shift
from sqlalchemy import inspect
from sqladmin import Admin, ModelView


from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse
from app.core.db import get_async_session
from app.crud.user_crud import crud_user
from app.validators.user_validators import check_password
from app.core.config import settings


def get_column_labels_from_comments(model):
    labels = {}
    mapper = inspect(model)  # получаем маппер модели
    for column in mapper.columns:
        if column.comment:  # если задан comment
            labels[getattr(model, column.name)] = column.comment
    return labels


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.name]
    column_labels = get_column_labels_from_comments(User)


class CafeAdmin(ModelView, model=Cafe):
    column_list = [Cafe.id, Cafe.name]
    column_labels = get_column_labels_from_comments(Cafe)


class ReservationAdmin(ModelView, model=Reservation):
    column_list = [Reservation.id, Reservation.status]
    column_labels = get_column_labels_from_comments(Reservation)


class ShiftAdmin(ModelView, model=Shift):
    column_list = [Shift.id, Shift.cafe_id]
    column_labels = get_column_labels_from_comments(Shift)


class CustomAuthBackend(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        telegram_id = form.get("telegram_id")
        password = form.get("password")
        session = await get_async_session().__anext__()
        user = await crud_user.get_by_telegram_id(telegram_id, session)
        await check_password(user, password)

        # авторизация успешна
        request.session.update({"user_id": telegram_id})
        return True

    async def logout(self, request: Request) -> RedirectResponse:
        request.session.clear()
        return RedirectResponse(url="/admin/login")

    async def authenticate(self, request: Request) -> bool:
        return "user_id" in request.session


# создаём админку с кастомной аутентификацией
auth_backend = CustomAuthBackend(secret_key=settings.secret)
