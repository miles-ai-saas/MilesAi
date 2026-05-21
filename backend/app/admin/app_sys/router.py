from fastapi import APIRouter

from app.admin.app_sys.views import auth

router = APIRouter()
router.include_router(auth.router)
