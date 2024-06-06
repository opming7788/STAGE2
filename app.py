from fastapi import *
from fastapi.responses import FileResponse
from fastapi import Path, Query, Request, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import mysql.connector

from fastapi.middleware.cors import CORSMiddleware

# 創建mysql連接池
dbconfig = {
    "host": "localhost",
    "user": "root",
    "password": "abc31415",
    
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