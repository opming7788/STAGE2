from fastapi import *
from fastapi.responses import FileResponse
from fastapi import Path, Query, Request, Depends, HTTPException,status
from typing import List, Optional
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import mysql.connector

# import auth

from fastapi.middleware.cors import CORSMiddleware


# 創建mysql連接池
dbconfig = {
    "host": "localhost",
    "user": "root",
    # "password":"xxxxxxxxxxxxxxxxx",
    
    "database": "taipeiattractions"
}

try:
    connection_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="mypool",
        pool_size=5,
        **dbconfig
    )
    print("Connection pool created successfully")
except mysql.connector.Error as e:
    print(f"Error creating connection pool: {e}")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],  # 允許的來源
    allow_credentials=True,
    allow_methods=["*"],  # 允許的方法
    allow_headers=["*"],  # 允許的標頭
)



from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")

# Static Pages (Never Modify Code in this Block)
@app.get("/", include_in_schema=False)
async def index(request: Request):
    return FileResponse("./static/index.html", media_type="text/html")

@app.get("/attraction/{id}", include_in_schema=False)
async def attraction(request: Request, id: int):
    return FileResponse("./static/attraction.html", media_type="text/html")

@app.get("/booking", include_in_schema=False)
async def booking(request: Request):
    return FileResponse("./static/booking.html", media_type="text/html")

@app.get("/thankyou", include_in_schema=False)
async def thankyou(request: Request):
    return FileResponse("./static/thankyou.html", media_type="text/html")

# ///////////////////////////////~我是分隔線~我是分隔線~////////////////////////////////////////

from datetime import datetime, timedelta,timezone
from fastapi.security import OAuth2PasswordBearer,OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from schemas import UserCreate, UserInDB, Token, RegistrationResponse, UserResponse

SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440 #24小時

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 驗證輸入的密碼是否與資料庫密碼相同
def verify_password(plain_password, hashed_password):
    # return pwd_context.verify(plain_password, hashed_password)
    if plain_password==hashed_password:
        return True
    return False

#密碼在加密
def get_password_hash(password):
    # return pwd_context.hash(password)
    return password

#輸入email返回user資料
def get_user(email: str):
    con = connection_pool.get_connection()
    try:
        with con.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM memberData WHERE email = %s", (email,))
            user = cursor.fetchone()
            # print(user)
            return user
    except mysql.connector.Error as e:
        print(f"Error fetching user: {e}")
        return None
    finally:
        if con:
            con.close()

#驗證輸入的email和密碼
def authenticate_user(email: str, password: str):
    user = get_user(email) #輸入email返回user資料

    #資料庫內若查無使用者則返回false
    if not user:
        return False

    # 驗證輸入的密碼是否與資料庫密碼相同，不同就返回false
    if not verify_password(password, user["hashed_password"]):
        return False
    return user

# 產生JWT的Token
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        # expire = datetime.utcnow() + expires_delta
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # expire = datetime.utcnow() + timedelta(minutes=15)
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# class RegistrationResponse(BaseModel):
#     ok: bool = True
   
# 註冊新會員
# @app.post("/signup", response_model=UserInDB)
@app.post("/api/user",response_model=RegistrationResponse, responses={
    400: {
        "description": "註冊失敗，重複的Email或其他原因",
        "content": {"application/json": {"example": {"error": "true", "message": "Email 已經註冊帳戶"}}}
    },
    500: {
        "description": "伺服器內部錯誤",
        "content": {"application/json": {"example": {"error": "true", "message": "內部伺服器錯誤"}}}
    },
})
def create_user(user: UserCreate):
    con = connection_pool.get_connection()
    try:
        with con.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM memberData WHERE email = %s", (user.email,))
            if cursor.fetchone():
                return JSONResponse(status_code=400, content={"error": "true","message": "Email 已經註冊帳戶"})
                # return HTTPException(status_code=400, detail="請按照情境提供對應的錯誤訊息")
        hashed_password = get_password_hash(user.password)
        
        with con.cursor(dictionary=True) as cursor:
            cursor.execute(
                "INSERT INTO memberData (username, email, hashed_password) VALUES (%s, %s, %s)",
                (user.username, user.email, hashed_password)
            )
            con.commit()
            user_id = cursor.lastrowid
        
        # return UserInDB(id=user_id, username=user.username, email=user.email)
        # return JSONResponse(status_code=200, content={"ok":true})
        return RegistrationResponse()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "true","message": "伺服器內部錯誤"})
    finally:
        con.close()

#登錄會員帳戶路由
# @app.post("/token", response_model=Token)
@app.put("/api/user/auth", response_model=Token ,responses={
    400: {
        "description": "登入失敗，帳號或密碼錯誤或其他原因",
        "content": {"application/json": {"example": {"error": "true", "message": "登入失敗，帳號或密碼錯誤或其他原因"}}}
    },
    500: {
        "description": "伺服器內部錯誤",
        "content": {"application/json": {"example": {"error": "true", "message": "伺服器內部錯誤"}}}
    },
})
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    #由於OAuth2PasswordRequestForm在FastAPI中默認只接受欄位username和password，
    #因此前端的代碼需要將郵箱位址放在username欄位中傳遞
    user = authenticate_user(form_data.username, form_data.password)
    
    try:
        if not user:
            # raise HTTPException(
            #     status_code=status.HTTP_401_UNAUTHORIZED,
            #     detail="Incorrect email or password",
            #     headers={"WWW-Authenticate": "Bearer"},
            # )
            return JSONResponse(status_code=400,content={"error": "true","message": "電子郵件或密碼錯誤"})
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        access_token = create_access_token(
            data={"sub": user["email"]}, expires_delta=access_token_expires
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "true","message": "伺服器內部錯誤"})
    # return {"access_token": access_token, "token_type": "bearer"}
    # return {"access_token": access_token}
    return {"token": access_token}




#給定jwt的Token解密後返回使用者資料user，取得當前會員資訊
@app.get("/api/user/auth", response_model=UserResponse)
def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if auth_header is None or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header.split(" ")[1]
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = get_user(email)
    if user is None:
        raise credentials_exception
    
    return UserResponse(data=UserInDB(**user))


# ////////////////////////////////////////////////Booking API////////////////////////////////////////////////////

from datetime import date
from decimal import Decimal
import json

@app.get("/api/booking")
async def get_booking(request: Request):
    auth_header = request.headers.get("Authorization")
    if auth_header is None or not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=403, content={"error": True,"message": "未登入系統，拒絕存取"})
    token = auth_header.split(" ")[1]
    con = connection_pool.get_connection()
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        member_email = payload["sub"]
        with con.cursor() as cursor:
            cursor.execute("SELECT memberData.id FROM memberData where memberData.email=%s",(member_email,))
            memberId=cursor.fetchone()[0]
            
            if memberId is None:
                return JSONResponse(status_code=404, content={"error": True, "message": "會員不存在"})

            # print("memberId:",memberId)
        with con.cursor() as cursor:
            cursor.execute("SELECT memberData.id ,BookingAttraction.attraction_id , BookingAttraction.Bookingdate ,\
            BookingAttraction.Bookingtime,BookingAttraction.price FROM memberData \
            JOIN BookingAttraction ON memberData.id = BookingAttraction.member_id \
            WHERE memberData.id =%s;", (memberId,))
            results = cursor.fetchall()
            # print(f"Query Results: {results}")

        if not results:
            return JSONResponse(status_code=200, content={"data": None})
          
        
        # con = connection_pool.get_connection()
        for item in results:
            attraction_id, booking_date, booking_time, price = item[1:]
            booking_date_str = booking_date.strftime("%Y-%m-%d")
            # print(item)
            # print(f"Processing attraction_id: {attraction_id}")
            with con.cursor() as cursor:
                cursor.execute("SELECT attractions.id,attractions.name,attractions.address ,images.image_url FROM attractions JOIN images ON attractions.id = images.attraction_id WHERE attractions.id = %s",(attraction_id,))
                attraction = cursor.fetchall()[0]
                # print("attraction:",attraction)

            attractionData = {
                "id": attraction[0],
                "name": attraction[1],
                "address": attraction[2],
                "image": attraction[3]
            }

            price_float = float(price) 

            bookingData = {
                "attraction": attractionData,
                # "date": booking_date,
                "date": booking_date_str,
                "time": booking_time,
                # "price": price
                "price": price_float
            }
        # print("bookingData:",bookingData)
        return JSONResponse(status_code=200, content={"data": bookingData})
        
    except Exception as e:
        print(f"Internal server error: {e}")
        return JSONResponse(status_code=500, content={"error": True, "message": "伺服器內部錯誤"})
    finally:
        con.close()

from typing import Literal

class BookingRequest(BaseModel):
    attractionId: int
    date: date
    time: Literal['morning', 'afternoon']
    price: float

@app.post("/api/booking")
async def post_booking(request: Request,booking: BookingRequest):
    con = connection_pool.get_connection()
    auth_header = request.headers.get("Authorization")
    if auth_header is None or not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=403, content={"error": True,"message": "未登入系統，拒絕存取"})
    
    token = auth_header.split(" ")[1]
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        with con.cursor() as cursor:
            cursor.execute("SELECT memberData.id FROM memberData where memberData.email=%s",(payload["sub"],))
            # print(cursor.fetchone())
            memberId=cursor.fetchone()
            # print("memberI:",memberId)
            if memberId is None:
                return JSONResponse(status_code=403, content={"error": True,"message": "未登入系統，拒絕存取"})
            memberId=memberId[0]
            cursor.execute("SELECT member_id FROM BookingAttraction WHERE member_id=%s",(memberId,))
            BookingAttractionMemberId=cursor.fetchone()
            if BookingAttractionMemberId is None:
                cursor.execute(
                    "INSERT INTO BookingAttraction (attraction_id, Bookingdate, Bookingtime,price,member_id) VALUES (%s, %s, %s,%s,%s)",
                    (booking.attractionId, booking.date,booking.time,booking.price,memberId)
                )
            else:
                # BookingAttractionMemberId=BookingAttractionMemberId[0]
                cursor.execute("UPDATE BookingAttraction SET attraction_id=%s, Bookingdate = %s, Bookingtime = %s, \
                price = %s WHERE member_id = %s;",(booking.attractionId, booking.date,booking.time,booking.price,memberId))

            con.commit()
        return JSONResponse(status_code=200, content={"ok": True})
    except JWTError:
        return JSONResponse(status_code=403, content={"error": True,"message": "未登入系統，拒絕存取"})
    except ValidationError as e:
        return JSONResponse(status_code=400, content={"error": True, "message": "建立失敗，輸入不正確或其他原因"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": True,"message": "伺服器內部錯誤"})
    finally:
        con.close()


@app.delete("/api/booking")
async def delete_booking(request: Request):
    con = connection_pool.get_connection()
    auth_header = request.headers.get("Authorization")
    if auth_header is None or not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=403, content={"error": True,"message": "未登入系統，拒絕存取"})
    token = auth_header.split(" ")[1]
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return JSONResponse(status_code=403, content={"error": True,"message": "未登入系統，拒絕存取"})
    
        user = get_user(email)
        if user is None:
            return JSONResponse(status_code=403, content={"error": True,"message": "未登入系統，拒絕存取"})
        print("user:",user["id"])

        
        with con.cursor() as cursor:
            cursor.execute("DELETE FROM BookingAttraction WHERE member_id = %s", (user["id"],))

            con.commit()
    except:
        return JSONResponse(status_code=500, content={"error": True,"message": "伺服器內部錯誤"})

    finally:
        con.close()

    return JSONResponse(status_code=200, content={"ok": True})
    




# ////////////////////////////////////////////////Booking API////////////////////////////////////////////////////



class Attraction(BaseModel):
    id: Optional[int]
    name: Optional[str]
    category: Optional[str]
    description: Optional[str]
    address: Optional[str]
    transport: Optional[str]
    mrt: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    images: Optional[List[str]]

class get_attractionResponse(BaseModel):
    data: Attraction

@app.get("/api/attraction/{attractionId}", response_model=get_attractionResponse)
async def get_attraction(request: Request, attractionId: int = Path(..., description="景點編號")):
    try:
        # 從連接池獲取連接
        # if attractionId is None:
        #     return JSONResponse(status_code=500,content={"error": True,"message": "請按照情境提供對應的錯誤訊息"})
        con = connection_pool.get_connection()
        with con.cursor() as cursor:
            cursor.execute("SELECT * FROM attractions WHERE attractions.id = %s", (attractionId,))
            rows = cursor.fetchall()
            if not rows:
                # raise HTTPException(status_code=400, detail={"error": True, "message": "景點編號不正確"})
                return JSONResponse(status_code=500,content={"error": True,"message": "請按照情境提供對應的錯誤訊息"})
            columnnames = [col[0] for col in cursor.description]

            cursor.execute("SELECT attractions.id, attractions.name, images.image_url FROM attractions \
            JOIN images ON attractions.id = images.attraction_id WHERE attractions.id = %s;", \
            (attractionId,))
            imgurls = cursor.fetchall()

            myimgList = []
            result = {}
            if rows:
                for i, columnname in enumerate(columnnames):
                    result[columnname] = rows[0][i]
                if imgurls:
                    for img in imgurls:
                        myimgList.append(img[2])
                    result["images"] = myimgList
            else:
                result = {}

        return {"data": result}
    # except HTTPException as e:
    #     raise e
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": "請按照情境提供對應的錯誤訊息"
            }
        )
    finally:
        if con.is_connected():
            con.close()

class AttractionResponse(BaseModel):
    nextPage: Optional[int]
    data: List[Attraction]

def get_page(page: int = Query(0, description="要取得的分頁，每頁 12 筆資料", ge=0)):
    return page

class ErrorResponse(BaseModel):
    error: bool
    message: str

@app.get("/api/attractions/", response_model=AttractionResponse)
async def attraction(request: Request, page: int = Depends(get_page),
                     keyword: str = Query(None, description="用來完全比對捷運站名稱、或模糊比對景點名稱的關鍵字，沒有給定則不做篩選")):
    try:
        con = connection_pool.get_connection()
        limitpage = 12
        offsetpage = page * limitpage
        with con.cursor() as cursor:
            if keyword:
                cursor.execute("SELECT COUNT(*) FROM attractions WHERE attractions.mrt LIKE %s \
                OR attractions.name LIKE %s;", ('%' + keyword + '%', '%' + keyword + '%'))
                TotalPageNum=cursor.fetchone()[0]
                cursor.execute("SELECT * FROM attractions WHERE attractions.mrt LIKE %s \
                OR attractions.name LIKE %s LIMIT %s OFFSET %s;", \
                ('%' + keyword + '%', '%' + keyword + '%', limitpage, offsetpage))
            else:
                cursor.execute("SELECT COUNT(*) FROM attractions")
                TotalPageNum=cursor.fetchone()[0]
                cursor.execute("SELECT * FROM attractions LIMIT %s OFFSET %s;", (limitpage, offsetpage))
            # print(TotalPageNum)
            rowsData = cursor.fetchall()
            columnnames = [col[0] for col in cursor.description]
            result = []
            if rowsData:
                for rows in rowsData:
                    mydic = dict(zip(columnnames, rows))
                    cursor.execute("SELECT attractions.id, attractions.name, images.image_url FROM attractions JOIN images ON attractions.id = images.attraction_id WHERE attractions.id = %s;", (mydic["id"],))
                    imgurls = cursor.fetchall()
                    myimgList = []
                    if imgurls:
                        for img in imgurls:
                            myimgList.append(img[2])
                        mydic["images"] = myimgList
                    result.append(mydic)

                if TotalPageNum%limitpage==0:
                    if (TotalPageNum/limitpage)==(page+1):
                        nextPage=None
                    else:
                        nextPage=page + 1
                    return {"nextPage": nextPage, "data": result}
                else:
                    if len(result)<limitpage:
                        nextPage=None
                    else:
                        nextPage=page + 1
                    return {"nextPage": nextPage, "data": result}     
            else:
                return {"nextPage": None, "data": result}
    except Exception as e:
        return JSONResponse(status_code=500,content={"error": True,"message": "請按照情境提供對應的錯誤訊息"})
        # raise HTTPException(status_code=500, detail=ErrorResponse(error=True, message="請按照情境提供對應的錯誤訊息"))
    finally:
        if con.is_connected():
            con.close()

class MRtsResponse(BaseModel):
    data: list

@app.get("/api/mrts", response_model=MRtsResponse)
async def get_mrts():
    try:
        con = connection_pool.get_connection()
        with con.cursor() as cursor:
            cursor.execute("SELECT mrt, COUNT(name) AS attraction_count FROM attractions GROUP BY mrt ORDER BY COUNT(name) DESC;")
            mrt_attractions = [row[0] for row in cursor.fetchall()]

        return {"data": mrt_attractions}
    except Exception as e:
        # return {
        #     "error": True,
        #     "message": "請按照情境提供對應的錯誤訊息"
        # }
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": "請按照情境提供對應的錯誤訊息"
            }
        )

    finally:
        if con.is_connected():
            con.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)