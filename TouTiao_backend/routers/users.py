import base64
import binascii
import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from models.users import User
from schemas.users import AvatarUploadRequest, UserRequest, UserAuthResponse, UserInfoResponse, UserUpdateRequest, UserChangePasswordRequest

from config.db_conf import get_db
from crud import users
from utils.response import success_response
from utils.auth import get_current_user
from config.settings import settings

router = APIRouter(prefix="/api/user", tags=["users"])


@router.post("/register")
async def register(user_data: UserRequest, db: AsyncSession = Depends(get_db)):  # 用户信息 和 db
    # 注册逻辑：验证用户是否存在 -> 创建用户 → 生成 Token  → 响应结果
    existing_user = await users.get_user_by_username(db, user_data.username)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户已存在")
    user = await users.create_user(db, user_data)
    token = await users.create_token(db, user.id)
    response_data = UserAuthResponse(token=token, user_info=UserInfoResponse.model_validate(user))
    return success_response(message="注册成功", data=response_data)


@router.post("/login")
async def login(user_data: UserRequest, db: AsyncSession = Depends(get_db)):
    # 登录逻辑：验证用户是否存在 -> 验证密码 -> 生成 Token  → 响应结果
    user = await users.authenticate_user(db, user_data.username, user_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = await users.create_token(db, user.id)
    response_data = UserAuthResponse(token=token, user_info=UserInfoResponse.model_validate(user))
    return success_response(message="登录成功啦", data=response_data)


# 查Token查用户 → 封装crud → 功能整合成一个工具函数 → 路由导入使用: 依赖注入
@router.get("/info")
async def get_user_info(user: User = Depends(get_current_user)):
    return success_response(message="获取用户信息成功", data=UserInfoResponse.model_validate(user))


# 修改用户信息：验证Token → 更新（用户输入数据 put 提交 → 请求体参数 → 定义Pydantic模型类） → 响应结果
# 参数：用户输入的 + 验证Token的 + db（调用更新的方法）
@router.put("/update")
async def update_user_info(user_data: UserUpdateRequest, user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    user = await users.update_user(db, user.username, user_data)
    return success_response(message="更新用户信息成功", data=UserInfoResponse.model_validate(user))


@router.put("/password")
async def update_password(
        password_data: UserChangePasswordRequest,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)):
    res_change_pwd = await users.change_password(db, user, password_data.old_password, password_data.new_password)
    if not res_change_pwd:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="修改密码失败，请稍后再试")
    return success_response(message="修改密码成功")


@router.post("/avatar")
async def upload_avatar(
        payload: AvatarUploadRequest,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)):
    match = re.fullmatch(r"data:image/(png|jpeg|jpg|webp);base64,(.+)", payload.image, re.DOTALL)
    if not match:
        raise HTTPException(status_code=400, detail="仅支持 PNG、JPEG 或 WebP 图片")
    extension = "jpg" if match.group(1) in {"jpeg", "jpg"} else match.group(1)
    try:
        content = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="头像数据无效") from exc
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="头像不能超过 2MB")

    settings.avatar_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{user.id}-{uuid4().hex[:12]}.{extension}"
    path = settings.avatar_dir / filename
    path.write_bytes(content)
    avatar_url = f"/uploads/avatars/{filename}"
    updated_user = await users.update_user(
        db, user.username, UserUpdateRequest(avatar=avatar_url)
    )
    return success_response("头像更新成功", UserInfoResponse.model_validate(updated_user))
