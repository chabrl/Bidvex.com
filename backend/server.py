from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Header, status, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError
from pathlib import Path
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest
import os
import logging
import uuid
import asyncio
import aiohttp

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
db_name = os.environ['DB_NAME']
jwt_secret = os.environ['JWT_SECRET']
stripe_api_key = os.environ['STRIPE_API_KEY']
google_maps_key = os.environ.get('GOOGLE_MAPS_API_KEY', '')

client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

import stripe
stripe.api_key = stripe_api_key

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, listing_id: str):
        await websocket.accept()
        if listing_id not in self.active_connections:
            self.active_connections[listing_id] = []
        self.active_connections[listing_id].append(websocket)

    def disconnect(self, websocket: WebSocket, listing_id: str):
        if listing_id in self.active_connections:
            self.active_connections[listing_id].remove(websocket)

    async def broadcast(self, listing_id: str, message: dict):
        if listing_id in self.active_connections:
            for connection in self.active_connections[listing_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass

manager = ConnectionManager()

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    account_type: str
    phone: str
    address: Optional[str] = None
    company_name: Optional[str] = None
    tax_number: Optional[str] = None
    bank_details: Optional[Dict[str, str]] = None

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    account_type: str
    phone: str
    phone_verified: bool = False
    address: Optional[str] = None
    company_name: Optional[str] = None
    tax_number: Optional[str] = None
    bank_details: Optional[Dict[str, str]] = None
    picture: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    language: str = "en"
    affiliate_code: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User

class ListingCreate(BaseModel):
    title: str
    description: str
    category: str
    condition: str
    starting_price: float
    buy_now_price: Optional[float] = None
    images: List[str] = []
    location: str
    city: str
    region: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    auction_end_date: datetime

class Listing(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    seller_id: str
    title: str
    description: str
    category: str
    condition: str
    starting_price: float
    current_price: float
    buy_now_price: Optional[float] = None
    images: List[str] = []
    location: str
    city: str
    region: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    auction_end_date: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "active"
    bid_count: int = 0
    is_promoted: bool = False
    views: int = 0

class BidCreate(BaseModel):
    listing_id: str
    amount: float

class Bid(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    listing_id: str
    bidder_id: str
    amount: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Category(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name_en: str
    name_fr: str
    icon: str

class SessionCreate(BaseModel):
    session_id: str

class MessageCreate(BaseModel):
    receiver_id: str
    content: str
    listing_id: Optional[str] = None

class Message(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    sender_id: str
    receiver_id: str
    listing_id: Optional[str] = None
    content: str
    is_read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Lot(BaseModel):
    lot_number: int
    title: str
    description: str
    quantity: int
    starting_price: float
    current_price: float
    condition: str
    images: List[str] = []

class MultiItemListingCreate(BaseModel):
    title: str
    description: str
    category: str
    location: str
    city: str
    region: str
    auction_end_date: datetime
    lots: List[Lot]

class MultiItemListing(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    seller_id: str
    title: str
    description: str
    category: str
    location: str
    city: str
    region: str
    auction_end_date: datetime
    lots: List[Lot]
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_lots: int = 0
    views: int = 0

class PaymentTransaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    user_id: Optional[str] = None
    listing_id: Optional[str] = None
    amount: float
    currency: str
    payment_status: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PaymentMethodCreate(BaseModel):
    payment_method_id: str

class PaymentMethodResponse(BaseModel):
    id: str
    user_id: str
    stripe_payment_method_id: str
    card_brand: str
    last4: str
    exp_month: int
    exp_year: int
    is_verified: bool
    is_default: bool

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    company_name: Optional[str] = None
    tax_number: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    language: Optional[str] = None
    picture: Optional[str] = None

class LocationSearchParams(BaseModel):
    latitude: float
    longitude: float
    radius_km: float = 50.0
    category: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, jwt_secret, algorithm="HS256")

async def get_current_user(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> User:
    token = None
    if "session_token" in request.cookies:
        token = request.cookies["session_token"]
    elif credentials:
        token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
        if not user_doc:
            raise HTTPException(status_code=401, detail="User not found")
        return User(**user_doc)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_pwd = hash_password(user_data.password)
    user = User(
        email=user_data.email, name=user_data.name, account_type=user_data.account_type,
        phone=user_data.phone, address=user_data.address, company_name=user_data.company_name,
        tax_number=user_data.tax_number, bank_details=user_data.bank_details
    )
    user_dict = user.model_dump()
    user_dict["password"] = hashed_pwd
    user_dict["created_at"] = user_dict["created_at"].isoformat()
    await db.users.insert_one(user_dict)
    token = create_access_token({"sub": user.id})
    return TokenResponse(access_token=token, user=user)

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user_doc = await db.users.find_one({"email": credentials.email})
    if not user_doc or not verify_password(credentials.password, user_doc["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user_doc.pop("password")
    user_doc.pop("_id")
    if isinstance(user_doc.get("created_at"), str):
        user_doc["created_at"] = datetime.fromisoformat(user_doc["created_at"])
    user = User(**user_doc)
    token = create_access_token({"sub": user.id})
    return TokenResponse(access_token=token, user=user)

@api_router.post("/auth/session")
async def process_session(session_data: SessionCreate):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_data.session_id}
        ) as response:
            if response.status != 200:
                raise HTTPException(status_code=400, detail="Invalid session")
            data = await response.json()
            existing_user = await db.users.find_one({"email": data["email"]})
            if not existing_user:
                user = User(
                    email=data["email"], name=data["name"], picture=data.get("picture"),
                    account_type="personal", phone="", phone_verified=False
                )
                user_dict = user.model_dump()
                user_dict["created_at"] = user_dict["created_at"].isoformat()
                await db.users.insert_one(user_dict)
                user_id = user.id
            else:
                user_id = existing_user["id"]
            session_token = create_access_token({"sub": user_id})
            session_doc = {
                "user_id": user_id, "session_token": data["session_token"],
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.sessions.insert_one(session_doc)
            return {"session_token": session_token}

@api_router.post("/auth/logout")
async def logout(current_user: User = Depends(get_current_user)):
    await db.sessions.delete_many({"user_id": current_user.id})
    return {"message": "Logged out successfully"}

@api_router.get("/auth/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@api_router.get("/users/{user_id}", response_model=User)
async def get_user(user_id: str):
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    if isinstance(user_doc.get("created_at"), str):
        user_doc["created_at"] = datetime.fromisoformat(user_doc["created_at"])
    return User(**user_doc)

@api_router.put("/users/me")
async def update_profile(updates: Dict[str, Any], current_user: User = Depends(get_current_user)):
    allowed_fields = ["name", "phone", "address", "company_name", "tax_number", "bank_details", "language", "picture"]
    update_data = {k: v for k, v in updates.items() if k in allowed_fields}
    if update_data:
        await db.users.update_one({"id": current_user.id}, {"$set": update_data})
    return {"message": "Profile updated successfully"}

@api_router.post("/listings", response_model=Listing)
async def create_listing(listing_data: ListingCreate, current_user: User = Depends(get_current_user)):
    listing = Listing(
        seller_id=current_user.id, title=listing_data.title, description=listing_data.description,
        category=listing_data.category, condition=listing_data.condition,
        starting_price=listing_data.starting_price, current_price=listing_data.starting_price,
        buy_now_price=listing_data.buy_now_price, images=listing_data.images,
        location=listing_data.location, city=listing_data.city, region=listing_data.region,
        latitude=listing_data.latitude, longitude=listing_data.longitude,
        auction_end_date=listing_data.auction_end_date
    )
    listing_dict = listing.model_dump()
    listing_dict["auction_end_date"] = listing_dict["auction_end_date"].isoformat()
    listing_dict["created_at"] = listing_dict["created_at"].isoformat()
    await db.listings.insert_one(listing_dict)
    return listing

@api_router.get("/listings", response_model=List[Listing])
async def get_listings(
    category: Optional[str] = None, city: Optional[str] = None, region: Optional[str] = None,
    condition: Optional[str] = None, min_price: Optional[float] = None, max_price: Optional[float] = None,
    search: Optional[str] = None, sort: str = "created_at", limit: int = 50, skip: int = 0
):
    query = {"status": "active"}
    if category:
        query["category"] = category
    if city:
        query["city"] = city
    if region:
        query["region"] = region
    if condition:
        query["condition"] = condition
    if min_price is not None:
        query["current_price"] = {"$gte": min_price}
    if max_price is not None:
        if "current_price" in query:
            query["current_price"]["$lte"] = max_price
        else:
            query["current_price"] = {"$lte": max_price}
    if search:
        query["$or"] = [{"title": {"$regex": search, "$options": "i"}}, {"description": {"$regex": search, "$options": "i"}}]
    sort_order = -1 if sort.startswith("-") else 1
    sort_field = sort.lstrip("-")
    listings = await db.listings.find(query, {"_id": 0}).sort(sort_field, sort_order).skip(skip).limit(limit).to_list(limit)
    for listing in listings:
        if isinstance(listing.get("created_at"), str):
            listing["created_at"] = datetime.fromisoformat(listing["created_at"])
        if isinstance(listing.get("auction_end_date"), str):
            listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
    return [Listing(**listing) for listing in listings]

@api_router.get("/listings/{listing_id}", response_model=Listing)
async def get_listing(listing_id: str):
    listing_doc = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing_doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    await db.listings.update_one({"id": listing_id}, {"$inc": {"views": 1}})
    if isinstance(listing_doc.get("created_at"), str):
        listing_doc["created_at"] = datetime.fromisoformat(listing_doc["created_at"])
    if isinstance(listing_doc.get("auction_end_date"), str):
        listing_doc["auction_end_date"] = datetime.fromisoformat(listing_doc["auction_end_date"])
    return Listing(**listing_doc)

@api_router.put("/listings/{listing_id}", response_model=Listing)
async def update_listing(listing_id: str, updates: Dict[str, Any], current_user: User = Depends(get_current_user)):
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["seller_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    allowed_fields = ["title", "description", "category", "condition", "images", "location", "city", "region", "status"]
    update_data = {k: v for k, v in updates.items() if k in allowed_fields}
    if update_data:
        await db.listings.update_one({"id": listing_id}, {"$set": update_data})
    updated_listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if isinstance(updated_listing.get("created_at"), str):
        updated_listing["created_at"] = datetime.fromisoformat(updated_listing["created_at"])
    if isinstance(updated_listing.get("auction_end_date"), str):
        updated_listing["auction_end_date"] = datetime.fromisoformat(updated_listing["auction_end_date"])
    return Listing(**updated_listing)

@api_router.delete("/listings/{listing_id}")
async def delete_listing(listing_id: str, current_user: User = Depends(get_current_user)):
    listing = await db.listings.find_one({"id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["seller_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    await db.listings.delete_one({"id": listing_id})
    return {"message": "Listing deleted successfully"}

@api_router.post("/bids", response_model=Bid)
async def place_bid(bid_data: BidCreate, current_user: User = Depends(get_current_user)):
    listing = await db.listings.find_one({"id": bid_data.listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["seller_id"] == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot bid on your own listing")
    if listing["status"] != "active":
        raise HTTPException(status_code=400, detail="Listing is not active")
    if isinstance(listing.get("auction_end_date"), str):
        auction_end = datetime.fromisoformat(listing["auction_end_date"])
    else:
        auction_end = listing["auction_end_date"]
    if datetime.now(timezone.utc) > auction_end:
        raise HTTPException(status_code=400, detail="Auction has ended")
    if bid_data.amount <= listing["current_price"]:
        raise HTTPException(status_code=400, detail="Bid must be higher than current price")
    bid = Bid(listing_id=bid_data.listing_id, bidder_id=current_user.id, amount=bid_data.amount)
    bid_dict = bid.model_dump()
    bid_dict["created_at"] = bid_dict["created_at"].isoformat()
    await db.bids.insert_one(bid_dict)
    await db.listings.update_one({"id": bid_data.listing_id}, {"$set": {"current_price": bid_data.amount}, "$inc": {"bid_count": 1}})
    await manager.broadcast(bid_data.listing_id, {"type": "new_bid", "bid": bid_dict, "current_price": bid_data.amount})
    return bid

@api_router.get("/bids/listing/{listing_id}", response_model=List[Bid])
async def get_listing_bids(listing_id: str, limit: int = 20):
    bids = await db.bids.find({"listing_id": listing_id}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    for bid in bids:
        if isinstance(bid.get("created_at"), str):
            bid["created_at"] = datetime.fromisoformat(bid["created_at"])
    return [Bid(**bid) for bid in bids]

@api_router.get("/categories", response_model=List[Category])
async def get_categories():
    categories = await db.categories.find({}, {"_id": 0}).to_list(100)
    return [Category(**cat) for cat in categories]

@api_router.post("/categories", response_model=Category)
async def create_category(category: Category, current_user: User = Depends(get_current_user)):
    cat_dict = category.model_dump()
    await db.categories.insert_one(cat_dict)
    return category

@api_router.get("/dashboard/seller")
async def get_seller_dashboard(current_user: User = Depends(get_current_user)):
    listings = await db.listings.find({"seller_id": current_user.id}, {"_id": 0}).to_list(1000)
    active_listings = [l for l in listings if l["status"] == "active"]
    sold_listings = [l for l in listings if l["status"] == "sold"]
    draft_listings = [l for l in listings if l["status"] == "draft"]
    total_sales = sum(l["current_price"] for l in sold_listings)
    return {
        "active_listings": len(active_listings), "sold_listings": len(sold_listings),
        "draft_listings": len(draft_listings), "total_sales": total_sales, "listings": listings
    }

@api_router.get("/dashboard/buyer")
async def get_buyer_dashboard(current_user: User = Depends(get_current_user)):
    bids = await db.bids.find({"bidder_id": current_user.id}, {"_id": 0}).to_list(1000)
    listing_ids = list(set(bid["listing_id"] for bid in bids))
    listings = await db.listings.find({"id": {"$in": listing_ids}}, {"_id": 0}).to_list(1000)
    return {
        "total_bids": len(bids),
        "active_bids": len([b for b in bids if any(l["status"] == "active" for l in listings if l["id"] == b["listing_id"])]),
        "won_items": len([l for l in listings if l["status"] == "sold"]), "bids": bids, "listings": listings
    }

@api_router.post("/payments/checkout")
async def create_checkout_session(request: Request, data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    listing_id = data.get("listing_id")
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    buyer_fee = 0.05 if current_user.account_type == "personal" else 0.045
    total_amount = listing["current_price"] * (1 + buyer_fee)
    host_url = str(request.base_url)
    success_url = f"{data.get('origin_url')}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{data.get('origin_url')}/listing/{listing_id}"
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    checkout_request = CheckoutSessionRequest(
        amount=total_amount, currency="usd", success_url=success_url, cancel_url=cancel_url,
        metadata={"user_id": current_user.id, "listing_id": listing_id, "buyer_fee": str(buyer_fee)}
    )
    session: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(checkout_request)
    transaction = PaymentTransaction(
        session_id=session.session_id, user_id=current_user.id, listing_id=listing_id,
        amount=total_amount, currency="usd", payment_status="pending", metadata=checkout_request.metadata
    )
    trans_dict = transaction.model_dump()
    trans_dict["created_at"] = trans_dict["created_at"].isoformat()
    await db.payment_transactions.insert_one(trans_dict)
    return {"url": session.url, "session_id": session.session_id}

@api_router.get("/payments/status/{session_id}")
async def get_payment_status(session_id: str, current_user: User = Depends(get_current_user)):
    webhook_url = "http://localhost:8001/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    status: CheckoutStatusResponse = await stripe_checkout.get_checkout_status(session_id)
    transaction = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if transaction and status.payment_status == "paid" and transaction["payment_status"] != "paid":
        await db.payment_transactions.update_one({"session_id": session_id}, {"$set": {"payment_status": "paid"}})
        listing_id = transaction.get("listing_id")
        if listing_id:
            await db.listings.update_one({"id": listing_id}, {"$set": {"status": "sold"}})
    return status.model_dump()

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")
    webhook_url = "http://localhost:8001/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    try:
        webhook_response = await stripe_checkout.handle_webhook(body, signature)
        if webhook_response.payment_status == "paid":
            await db.payment_transactions.update_one({"session_id": webhook_response.session_id}, {"$set": {"payment_status": "paid"}})
            transaction = await db.payment_transactions.find_one({"session_id": webhook_response.session_id})
            if transaction and transaction.get("listing_id"):
                await db.listings.update_one({"id": transaction["listing_id"]}, {"$set": {"status": "sold"}})
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=400, detail="Webhook error")

@app.websocket("/ws/listings/{listing_id}")
async def websocket_endpoint(websocket: WebSocket, listing_id: str):
    await manager.connect(websocket, listing_id)
    try:
        while True:
            data = await websocket.receive_text()
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(websocket, listing_id)

@api_router.post("/payment-methods")
async def add_payment_method(data: PaymentMethodCreate, current_user: User = Depends(get_current_user)):
    try:
        payment_method = stripe.PaymentMethod.retrieve(data.payment_method_id)
        stripe.PaymentMethod.attach(data.payment_method_id, customer=current_user.id)
        
        intent = stripe.PaymentIntent.create(
            amount=100,
            currency='usd',
            payment_method=data.payment_method_id,
            customer=current_user.id,
            confirm=True,
            return_url='https://bazario-mvp.preview.emergentagent.com'
        )
        
        is_verified = intent.status == 'succeeded' or intent.status == 'requires_capture'
        
        pm_doc = {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "stripe_payment_method_id": data.payment_method_id,
            "card_brand": payment_method.card.brand,
            "last4": payment_method.card.last4,
            "exp_month": payment_method.card.exp_month,
            "exp_year": payment_method.card.exp_year,
            "is_verified": is_verified,
            "is_default": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.payment_methods.insert_one(pm_doc)
        
        if is_verified:
            stripe.PaymentIntent.cancel(intent.id)
        
        return PaymentMethodResponse(**pm_doc)
    except Exception as e:
        logger.error(f"Payment method error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.get("/payment-methods")
async def get_payment_methods(current_user: User = Depends(get_current_user)):
    methods = await db.payment_methods.find({"user_id": current_user.id}, {"_id": 0}).to_list(100)
    return methods

@api_router.delete("/payment-methods/{method_id}")
async def delete_payment_method(method_id: str, current_user: User = Depends(get_current_user)):
    method = await db.payment_methods.find_one({"id": method_id, "user_id": current_user.id})
    if not method:
        raise HTTPException(status_code=404, detail="Payment method not found")
    
    try:
        stripe.PaymentMethod.detach(method["stripe_payment_method_id"])
    except:
        pass
    
    await db.payment_methods.delete_one({"id": method_id})
    return {"message": "Payment method deleted"}

@api_router.put("/profile")
async def update_profile(updates: ProfileUpdate, current_user: User = Depends(get_current_user)):
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    if update_data:
        await db.users.update_one({"id": current_user.id}, {"$set": update_data})
    updated_user = await db.users.find_one({"id": current_user.id}, {"_id": 0, "password": 0})
    return updated_user

@api_router.post("/listings/search/location")
async def search_by_location(params: LocationSearchParams):
    query = {"status": "active"}
    
    if params.category:
        query["category"] = params.category
    if params.min_price is not None:
        query["current_price"] = {"$gte": params.min_price}
    if params.max_price is not None:
        if "current_price" in query:
            query["current_price"]["$lte"] = params.max_price
        else:
            query["current_price"] = {"$lte": params.max_price}
    
    if params.latitude and params.longitude:
        radius_in_radians = params.radius_km / 6371.0
        query["$or"] = [
            {
                "latitude": {
                    "$gte": params.latitude - radius_in_radians * 57.2958,
                    "$lte": params.latitude + radius_in_radians * 57.2958
                },
                "longitude": {
                    "$gte": params.longitude - radius_in_radians * 57.2958,
                    "$lte": params.longitude + radius_in_radians * 57.2958
                }
            },
            {"latitude": None}
        ]
    
    listings = await db.listings.find(query, {"_id": 0}).limit(50).to_list(50)
    
    for listing in listings:
        if isinstance(listing.get("created_at"), str):
            listing["created_at"] = datetime.fromisoformat(listing["created_at"])
        if isinstance(listing.get("auction_end_date"), str):
            listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
    
    return [Listing(**listing) for listing in listings]

@api_router.get("/config/google-maps-key")
async def get_google_maps_key():
    return {"api_key": google_maps_key}

@api_router.get("/affiliate/stats")
async def get_affiliate_stats(current_user: User = Depends(get_current_user)):
    referrals = await db.referrals.find({"affiliate_id": current_user.id}, {"_id": 0}).to_list(1000)
    
    total_referrals = len(referrals)
    active_referrals = len([r for r in referrals if r.get("status") == "active"])
    
    earnings = await db.affiliate_earnings.find({"affiliate_id": current_user.id}, {"_id": 0}).to_list(1000)
    total_earnings = sum(e.get("commission_amount", 0) for e in earnings)
    pending_earnings = sum(e.get("commission_amount", 0) for e in earnings if e.get("status") == "pending")
    paid_earnings = sum(e.get("commission_amount", 0) for e in earnings if e.get("status") == "paid")
    
    return {
        "affiliate_code": current_user.affiliate_code,
        "referral_link": f"https://bazario-mvp.preview.emergentagent.com/auth?ref={current_user.affiliate_code}",
        "total_referrals": total_referrals,
        "active_referrals": active_referrals,
        "total_earnings": total_earnings,
        "pending_earnings": pending_earnings,
        "paid_earnings": paid_earnings,
        "earnings_history": earnings,
        "referrals": referrals
    }

@api_router.post("/affiliate/withdraw")
async def request_withdrawal(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    amount = data.get("amount")
    method = data.get("method", "bank_transfer")
    
    earnings = await db.affiliate_earnings.find({
        "affiliate_id": current_user.id,
        "status": "pending"
    }).to_list(1000)
    
    available = sum(e.get("commission_amount", 0) for e in earnings)
    
    if amount > available:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    withdrawal_request = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "amount": amount,
        "method": method,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.withdrawal_requests.insert_one(withdrawal_request)
    
    return {"message": "Withdrawal request submitted", "request_id": withdrawal_request["id"]}

@api_router.post("/messages")
async def send_message(msg: MessageCreate, current_user: User = Depends(get_current_user)):
    conversation_id = "_".join(sorted([current_user.id, msg.receiver_id]))
    
    message = Message(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        receiver_id=msg.receiver_id,
        listing_id=msg.listing_id,
        content=msg.content
    )
    
    msg_dict = message.model_dump()
    msg_dict["created_at"] = msg_dict["created_at"].isoformat()
    await db.messages.insert_one(msg_dict)
    
    await db.conversations.update_one(
        {"id": conversation_id},
        {
            "$set": {
                "last_message": msg.content,
                "last_message_at": datetime.now(timezone.utc).isoformat()
            },
            "$setOnInsert": {
                "id": conversation_id,
                "participants": [current_user.id, msg.receiver_id],
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    
    await manager.send_to_user(msg.receiver_id, {
        "type": "new_message",
        "message": msg_dict
    })
    
    return message

@api_router.get("/conversations")
async def get_conversations(current_user: User = Depends(get_current_user)):
    convos = await db.conversations.find(
        {"participants": current_user.id},
        {"_id": 0}
    ).sort("last_message_at", -1).to_list(100)
    
    for convo in convos:
        other_user_id = [p for p in convo["participants"] if p != current_user.id][0]
        user = await db.users.find_one({"id": other_user_id}, {"_id": 0, "password": 0, "name": 1, "picture": 1})
        convo["other_user"] = user
        
        unread = await db.messages.count_documents({
            "conversation_id": convo["id"],
            "receiver_id": current_user.id,
            "is_read": False
        })
        convo["unread_count"] = unread
    
    return convos

@api_router.get("/messages/{conversation_id}")
async def get_messages(conversation_id: str, current_user: User = Depends(get_current_user), limit: int = 50):
    messages = await db.messages.find(
        {"conversation_id": conversation_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    await db.messages.update_many(
        {"conversation_id": conversation_id, "receiver_id": current_user.id},
        {"$set": {"is_read": True}}
    )
    
    for msg in messages:
        if isinstance(msg.get("created_at"), str):
            msg["created_at"] = datetime.fromisoformat(msg["created_at"])
    
    return [Message(**msg) for msg in reversed(messages)]

@api_router.post("/multi-item-listings")
async def create_multi_item_listing(listing_data: MultiItemListingCreate, current_user: User = Depends(get_current_user)):
    if current_user.account_type != "business":
        raise HTTPException(status_code=403, detail="Only business accounts can create multi-item listings")
    
    listing = MultiItemListing(
        seller_id=current_user.id,
        title=listing_data.title,
        description=listing_data.description,
        category=listing_data.category,
        location=listing_data.location,
        city=listing_data.city,
        region=listing_data.region,
        auction_end_date=listing_data.auction_end_date,
        lots=[lot.model_dump() for lot in listing_data.lots],
        total_lots=len(listing_data.lots)
    )
    
    listing_dict = listing.model_dump()
    listing_dict["auction_end_date"] = listing_dict["auction_end_date"].isoformat()
    listing_dict["created_at"] = listing_dict["created_at"].isoformat()
    
    await db.multi_item_listings.insert_one(listing_dict)
    
    return listing

@api_router.get("/multi-item-listings")
async def get_multi_item_listings(limit: int = 50, skip: int = 0):
    listings = await db.multi_item_listings.find(
        {"status": "active"},
        {"_id": 0}
    ).skip(skip).limit(limit).to_list(limit)
    
    for listing in listings:
        if isinstance(listing.get("created_at"), str):
            listing["created_at"] = datetime.fromisoformat(listing["created_at"])
        if isinstance(listing.get("auction_end_date"), str):
            listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
    
    return [MultiItemListing(**listing) for listing in listings]

@api_router.get("/multi-item-listings/{listing_id}")
async def get_multi_item_listing(listing_id: str):
    listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    if isinstance(listing.get("created_at"), str):
        listing["created_at"] = datetime.fromisoformat(listing["created_at"])
    if isinstance(listing.get("auction_end_date"), str):
        listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
    
    return MultiItemListing(**listing)

@api_router.post("/multi-item-listings/{listing_id}/lots/{lot_number}/bid")
async def bid_on_lot(listing_id: str, lot_number: int, data: Dict[str, float], current_user: User = Depends(get_current_user)):
    listing = await db.multi_item_listings.find_one({"id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    if listing["seller_id"] == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot bid on your own listing")
    
    amount = data.get("amount")
    lots = listing["lots"]
    
    lot_index = next((i for i, lot in enumerate(lots) if lot["lot_number"] == lot_number), None)
    if lot_index is None:
        raise HTTPException(status_code=404, detail="Lot not found")
    
    if amount <= lots[lot_index]["current_price"]:
        raise HTTPException(status_code=400, detail="Bid must be higher than current price")
    
    lots[lot_index]["current_price"] = amount
    
    await db.multi_item_listings.update_one(
        {"id": listing_id},
        {"$set": {"lots": lots}}
    )
    
    bid = {
        "id": str(uuid.uuid4()),
        "listing_id": listing_id,
        "lot_number": lot_number,
        "bidder_id": current_user.id,
        "amount": amount,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.lot_bids.insert_one(bid)
    
    return {"message": "Bid placed successfully", "bid": bid}

@app.websocket("/ws/messages/{user_id}")
async def websocket_messages(websocket: WebSocket, user_id: str):
    await manager.connect_user(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        manager.disconnect_user(user_id)

@api_router.get("/admin/users")
async def admin_get_users(current_user: User = Depends(get_current_user), limit: int = 100, skip: int = 0):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    users = await db.users.find({}, {"_id": 0, "password": 0}).skip(skip).limit(limit).to_list(limit)
    return users

@api_router.put("/admin/users/{user_id}/status")
async def admin_update_user_status(user_id: str, data: Dict[str, str], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    await db.users.update_one({"id": user_id}, {"$set": {"status": data.get("status")}})
    return {"message": "User status updated"}

@api_router.get("/admin/reports")
async def admin_get_reports(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    reports = await db.reports.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return reports

@api_router.post("/notifications")
async def create_notification(data: Dict[str, Any]):
    notification = {
        "id": str(uuid.uuid4()),
        "user_id": data.get("user_id"),
        "type": data.get("type"),
        "title": data.get("title"),
        "content": data.get("content"),
        "link": data.get("link"),
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.notifications.insert_one(notification)
    await manager.send_to_user(data.get("user_id"), {"type": "notification", "data": notification})
    return notification

@api_router.get("/notifications")
async def get_notifications(current_user: User = Depends(get_current_user), limit: int = 50):
    notifications = await db.notifications.find(
        {"user_id": current_user.id},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return notifications

@api_router.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: User = Depends(get_current_user)):
    await db.notifications.update_one(
        {"id": notification_id, "user_id": current_user.id},
        {"$set": {"is_read": True}}
    )
    return {"message": "Notification marked as read"}

@api_router.post("/promotions")
async def create_promotion(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    promotion = {
        "id": str(uuid.uuid4()),
        "listing_id": data.get("listing_id"),
        "seller_id": current_user.id,
        "promotion_type": data.get("promotion_type"),
        "price": data.get("price"),
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": data.get("end_date"),
        "targeting": data.get("targeting", {}),
        "impressions": 0,
        "clicks": 0,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.promotions.insert_one(promotion)
    await db.listings.update_one({"id": data.get("listing_id")}, {"$set": {"is_promoted": True}})
    return promotion

@api_router.get("/promotions/my")
async def get_my_promotions(current_user: User = Depends(get_current_user)):
    promotions = await db.promotions.find(
        {"seller_id": current_user.id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return promotions

@api_router.get("/stats/top-sellers")
async def get_top_sellers(limit: int = 10):
    pipeline = [
        {"$match": {"status": "sold"}},
        {"$group": {"_id": "$seller_id", "total_sales": {"$sum": "$current_price"}, "count": {"$sum": 1}}},
        {"$sort": {"total_sales": -1}},
        {"$limit": limit}
    ]
    results = await db.listings.aggregate(pipeline).to_list(limit)
    
    sellers = []
    for result in results:
        user = await db.users.find_one({"id": result["_id"]}, {"_id": 0, "password": 0})
        if user:
            sellers.append({
                "user": user,
                "total_sales": result["total_sales"],
                "items_sold": result["count"]
            })
    return sellers

@api_router.get("/stats/hot-items")
async def get_hot_items(limit: int = 10):
    listings = await db.listings.find(
        {"status": "active"},
        {"_id": 0}
    ).sort("views", -1).limit(limit).to_list(limit)
    
    for listing in listings:
        if isinstance(listing.get("created_at"), str):
            listing["created_at"] = datetime.fromisoformat(listing["created_at"])
        if isinstance(listing.get("auction_end_date"), str):
            listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
    
    return [Listing(**listing) for listing in listings]

@api_router.get("/")
async def root():
    return {"message": "Bazario API v1.0"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware, allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"], allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

@app.on_event("startup")
async def seed_categories():
    existing_categories = await db.categories.count_documents({})
    if existing_categories == 0:
        categories = [
            {"id": str(uuid.uuid4()), "name_en": "Electronics", "name_fr": "Électronique", "icon": "laptop"},
            {"id": str(uuid.uuid4()), "name_en": "Fashion", "name_fr": "Mode", "icon": "shirt"},
            {"id": str(uuid.uuid4()), "name_en": "Home & Garden", "name_fr": "Maison & Jardin", "icon": "home"},
            {"id": str(uuid.uuid4()), "name_en": "Sports", "name_fr": "Sports", "icon": "dumbbell"},
            {"id": str(uuid.uuid4()), "name_en": "Vehicles", "name_fr": "Véhicules", "icon": "car"},
            {"id": str(uuid.uuid4()), "name_en": "Art & Collectibles", "name_fr": "Art & Objets de collection", "icon": "palette"},
            {"id": str(uuid.uuid4()), "name_en": "Books & Media", "name_fr": "Livres & Médias", "icon": "book"},
            {"id": str(uuid.uuid4()), "name_en": "Toys & Games", "name_fr": "Jouets & Jeux", "icon": "gamepad-2"},
        ]
        await db.categories.insert_many(categories)
        logger.info("Categories seeded successfully")
