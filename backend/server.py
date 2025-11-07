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
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
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

# Scheduled job to transition upcoming auctions to active
async def transition_upcoming_auctions():
    """
    Background task that runs every 5 minutes to check for upcoming auctions
    whose start date has passed and transitions them to 'active' status.
    """
    try:
        now = datetime.now(timezone.utc)
        
        # Find all upcoming auctions where start date has passed
        upcoming_auctions = await db.multi_item_listings.find({
            "status": "upcoming",
            "auction_start_date": {"$lte": now.isoformat()}
        }).to_list(100)
        
        transition_count = 0
        for auction in upcoming_auctions:
            # Update status to active
            await db.multi_item_listings.update_one(
                {"id": auction["id"]},
                {"$set": {"status": "active"}}
            )
            transition_count += 1
            logger.info(f"Transitioned auction {auction['id']} from upcoming to active")
        
        if transition_count > 0:
            logger.info(f"✅ Transitioned {transition_count} upcoming auction(s) to active")
        
    except Exception as e:
        logger.error(f"❌ Error in transition_upcoming_auctions: {str(e)}")

# Initialize APScheduler
scheduler = AsyncIOScheduler()
scheduler.add_job(
    transition_upcoming_auctions,
    trigger=IntervalTrigger(minutes=5),
    id='transition_upcoming_auctions',
    name='Transition upcoming auctions to active',
    replace_existing=True
)

# Start scheduler on app startup
@app.on_event("startup")
async def start_scheduler():
    scheduler.start()
    logger.info("🚀 APScheduler started - checking for upcoming auctions every 5 minutes")

@app.on_event("shutdown")
async def shutdown_scheduler():
    scheduler.shutdown()
    logger.info("🛑 APScheduler shut down")

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
    billing_address: Optional[str] = None  # For invoicing

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
    auction_start_date: Optional[datetime] = None
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
    auction_start_date: Optional[datetime] = None
    lots: List[Lot]
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_lots: int = 0
    views: int = 0
    # Invoice configuration
    premium_percentage: float = 5.0  # Buyer's premium (5%)
    commission_rate: float = 15.0     # Seller commission (15%)
    tax_rate_gst: float = 5.0         # GST (5%)
    tax_rate_qst: float = 9.975       # QST (9.975%)
    payment_deadline: Optional[datetime] = None
    pickup_locations: Optional[List[Dict[str, Any]]] = None  # [{address, hours, deadline}]

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

class PaddleNumber(BaseModel):
    """Paddle number assignment for buyer in specific auction"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    auction_id: str
    user_id: str
    paddle_number: int
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Invoice(BaseModel):
    """Invoice/document generation tracking"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    invoice_number: str  # BV-2025-AUC123-0001
    invoice_type: str    # 'lots_won', 'payment_letter', 'seller_statement', etc.
    user_id: str
    auction_id: str
    pdf_path: str
    generated_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "generated"  # 'generated', 'sent', 'viewed', 'paid'

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

@api_router.get("/bids/listing/{listing_id}")
async def get_listing_bids(listing_id: str, limit: int = 20):
    """Get bids for a listing with bidder information"""
    bids = await db.bids.find({"listing_id": listing_id}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Enrich bids with bidder information
    enriched_bids = []
    for bid in bids:
        # Get bidder user info
        bidder = await db.users.find_one({"id": bid["bidder_id"]}, {"_id": 0, "name": 1, "picture": 1})
        
        # Format datetime
        if isinstance(bid.get("created_at"), str):
            bid["created_at"] = datetime.fromisoformat(bid["created_at"])
        
        enriched_bids.append({
            **bid,
            "bidder_name": bidder.get("name") if bidder else "Anonymous",
            "bidder_avatar": bidder.get("picture") if bidder else None,
            "created_at": bid["created_at"].isoformat() if isinstance(bid["created_at"], datetime) else bid["created_at"]
        })
    
    return enriched_bids

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
    
    # Fetch watchlist items
    watchlist_items = await db.watchlist.find({"user_id": current_user.id}, {"_id": 0}).to_list(100)
    watchlist_listing_ids = [item["listing_id"] for item in watchlist_items]
    watchlist_listings = await db.listings.find(
        {"id": {"$in": watchlist_listing_ids}, "status": {"$ne": "deleted"}},
        {"_id": 0}
    ).to_list(100)
    
    return {
        "total_bids": len(bids),
        "active_bids": len([b for b in bids if any(l["status"] == "active" for l in listings if l["id"] == b["listing_id"])]),
        "won_items": len([l for l in listings if l["status"] == "sold"]),
        "bids": bids,
        "listings": listings,
        "watchlist": watchlist_listings
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
            # Handle promotion payment
            if transaction and transaction.get("metadata") and transaction["metadata"].get("promotion_id"):
                promotion_id = transaction["metadata"]["promotion_id"]
                await db.promotions.update_one({"id": promotion_id}, {"$set": {"status": "active", "payment_status": "paid"}})
                promotion = await db.promotions.find_one({"id": promotion_id})
                if promotion and promotion.get("listing_id"):
                    await db.listings.update_one({"id": promotion["listing_id"]}, {"$set": {"is_promoted": True}})
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=400, detail="Webhook error")

@api_router.post("/payments/promote")
async def create_promotion_checkout(request: Request, data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    promotion_id = data.get("promotion_id")
    amount = data.get("amount")
    
    if not promotion_id or not amount:
        raise HTTPException(status_code=400, detail="Missing promotion_id or amount")
    
    promotion = await db.promotions.find_one({"id": promotion_id}, {"_id": 0})
    if not promotion:
        raise HTTPException(status_code=404, detail="Promotion not found")
    
    if promotion["seller_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    host_url = str(request.base_url)
    success_url = f"{data.get('origin_url')}/listing/{promotion['listing_id']}?promoted=true"
    cancel_url = f"{data.get('origin_url')}/listing/{promotion['listing_id']}"
    webhook_url = f"{host_url}api/webhook/stripe"
    
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    checkout_request = CheckoutSessionRequest(
        amount=amount, 
        currency="usd", 
        success_url=success_url, 
        cancel_url=cancel_url,
        metadata={"user_id": current_user.id, "promotion_id": promotion_id, "listing_id": promotion["listing_id"]}
    )
    
    session: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(checkout_request)
    
    transaction = PaymentTransaction(
        session_id=session.session_id, 
        user_id=current_user.id, 
        listing_id=promotion["listing_id"],
        amount=amount, 
        currency="usd", 
        payment_status="pending", 
        metadata={"promotion_id": promotion_id, **checkout_request.metadata}
    )
    trans_dict = transaction.model_dump()
    trans_dict["created_at"] = trans_dict["created_at"].isoformat()
    await db.payment_transactions.insert_one(trans_dict)
    
    return {"url": session.url, "session_id": session.session_id}

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
            return_url='https://lot-wizard.preview.emergentagent.com'
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
        "referral_link": f"https://lot-wizard.preview.emergentagent.com/auth?ref={current_user.affiliate_code}",
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
    
    # Determine status based on auction_start_date
    now = datetime.now(timezone.utc)
    status = "active"  # Default to active
    
    if listing_data.auction_start_date:
        # If start date is in the future, set to upcoming
        if listing_data.auction_start_date > now:
            status = "upcoming"
    
    listing = MultiItemListing(
        seller_id=current_user.id,
        title=listing_data.title,
        description=listing_data.description,
        category=listing_data.category,
        location=listing_data.location,
        city=listing_data.city,
        region=listing_data.region,
        auction_end_date=listing_data.auction_end_date,
        auction_start_date=listing_data.auction_start_date,
        lots=[lot.model_dump() for lot in listing_data.lots],
        total_lots=len(listing_data.lots),
        status=status
    )
    
    listing_dict = listing.model_dump()
    listing_dict["auction_end_date"] = listing_dict["auction_end_date"].isoformat()
    listing_dict["created_at"] = listing_dict["created_at"].isoformat()
    if listing_dict["auction_start_date"]:
        listing_dict["auction_start_date"] = listing_dict["auction_start_date"].isoformat()
    
    await db.multi_item_listings.insert_one(listing_dict)
    
    return listing

@api_router.get("/multi-item-listings")
async def get_multi_item_listings(limit: int = 50, skip: int = 0, status: Optional[str] = None):
    # Build query filter
    query = {}
    if status:
        query["status"] = status
    else:
        # Default to active listings if no status specified
        query["status"] = "active"
    
    listings = await db.multi_item_listings.find(
        query,
        {"_id": 0}
    ).skip(skip).limit(limit).to_list(limit)
    
    for listing in listings:
        if isinstance(listing.get("created_at"), str):
            listing["created_at"] = datetime.fromisoformat(listing["created_at"])
        if isinstance(listing.get("auction_end_date"), str):
            listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
        if isinstance(listing.get("auction_start_date"), str):
            listing["auction_start_date"] = datetime.fromisoformat(listing["auction_start_date"])
    
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
    if isinstance(listing.get("auction_start_date"), str):
        listing["auction_start_date"] = datetime.fromisoformat(listing["auction_start_date"])
    
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

@api_router.get("/admin/listings/pending")
async def admin_get_pending_listings(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    listings = await db.listings.find({"status": "pending"}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [Listing(**listing) for listing in listings]

@api_router.put("/admin/listings/{listing_id}/moderate")
async def admin_moderate_listing(listing_id: str, data: Dict[str, str], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    action = data.get("action")
    if action == "approve":
        await db.listings.update_one({"id": listing_id}, {"$set": {"status": "active"}})
    elif action == "reject":
        await db.listings.update_one({"id": listing_id}, {"$set": {"status": "rejected"}})
    elif action == "remove":
        await db.listings.delete_one({"id": listing_id})
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    return {"message": f"Listing {action}d successfully"}

@api_router.get("/admin/transactions")
async def admin_get_transactions(current_user: User = Depends(get_current_user), limit: int = 50):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    transactions = await db.payment_transactions.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return transactions

@api_router.get("/admin/analytics")
async def admin_get_analytics(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    active_listings = await db.listings.count_documents({"status": "active"})
    total_users = await db.users.count_documents({})
    
    # Calculate total revenue from paid transactions
    paid_transactions = await db.payment_transactions.find({"payment_status": "paid"}, {"_id": 0, "amount": 1}).to_list(1000)
    total_revenue = sum([tx.get("amount", 0) for tx in paid_transactions])
    
    return {
        "active_listings": active_listings,
        "total_users": total_users,
        "total_revenue": total_revenue
    }

# ============================================
# SPRINT 1: OPERATIONS CONTROL ENDPOINTS
# ============================================

# PROMOTION MANAGEMENT
@api_router.get("/admin/promotions")
async def admin_get_promotions(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    promotions = await db.promotions.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return promotions

@api_router.post("/admin/promotions/create")
async def admin_create_promotion(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    promotion = {
        "id": str(uuid.uuid4()),
        "listing_id": data.get("listing_id"),
        "promotion_type": data.get("promotion_type"),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "end_date": data.get("end_date")
    }
    await db.promotions.insert_one(promotion)
    await db.listings.update_one({"id": data.get("listing_id")}, {"$set": {"is_promoted": True}})
    return promotion

@api_router.delete("/admin/promotions/{promotion_id}")
async def admin_delete_promotion(promotion_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    promotion = await db.promotions.find_one({"id": promotion_id})
    if promotion:
        await db.listings.update_one({"id": promotion.get("listing_id")}, {"$set": {"is_promoted": False}})
        await db.promotions.delete_one({"id": promotion_id})
    return {"message": "Promotion deleted"}

@api_router.put("/admin/listings/{listing_id}/feature")
async def admin_feature_listing(listing_id: str, data: Dict[str, bool], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    is_featured = data.get("is_featured", False)
    await db.listings.update_one({"id": listing_id}, {"$set": {"is_featured": is_featured}})
    return {"message": f"Listing {'featured' if is_featured else 'unfeatured'}"}

# CATEGORY MANAGEMENT
@api_router.post("/admin/categories")
async def admin_create_category(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    category = {
        "id": str(uuid.uuid4()),
        "name_en": data.get("name_en"),
        "name_fr": data.get("name_fr"),
        "icon": data.get("icon", "📦"),
        "order": data.get("order", 0),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.categories.insert_one(category)
    return category

@api_router.put("/admin/categories/{category_id}")
async def admin_update_category(category_id: str, data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.categories.update_one({"id": category_id}, {"$set": data})
    return {"message": "Category updated"}

@api_router.delete("/admin/categories/{category_id}")
async def admin_delete_category(category_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.categories.delete_one({"id": category_id})
    return {"message": "Category deleted"}

# AUCTION LIFECYCLE CONTROL
@api_router.get("/admin/auctions")
async def admin_get_auctions(status: str = None, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = {}
    if status:
        query["status"] = status
    
    listings = await db.listings.find(query, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    return [Listing(**listing) for listing in listings]

@api_router.put("/admin/auctions/{listing_id}/pause")
async def admin_pause_auction(listing_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.listings.update_one({"id": listing_id}, {"$set": {"status": "paused"}})
    return {"message": "Auction paused"}

@api_router.put("/admin/auctions/{listing_id}/resume")
async def admin_resume_auction(listing_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.listings.update_one({"id": listing_id}, {"$set": {"status": "active"}})
    return {"message": "Auction resumed"}

@api_router.put("/admin/auctions/{listing_id}/extend")
async def admin_extend_auction(listing_id: str, data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    new_end_date = data.get("new_end_date")
    await db.listings.update_one({"id": listing_id}, {"$set": {"auction_end_date": new_end_date}})
    return {"message": "Auction extended"}

@api_router.delete("/admin/auctions/{listing_id}/cancel")
async def admin_cancel_auction(listing_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.listings.update_one({"id": listing_id}, {"$set": {"status": "cancelled"}})
    return {"message": "Auction cancelled"}

# AFFILIATE PROGRAM MANAGEMENT
@api_router.get("/admin/affiliates")
async def admin_get_affiliates(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    affiliates = await db.affiliates.find({}, {"_id": 0}).to_list(100)
    return affiliates

@api_router.put("/admin/users/{user_id}/affiliate")
async def admin_set_affiliate_status(user_id: str, data: Dict[str, bool], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    is_affiliate = data.get("is_affiliate", False)
    if is_affiliate:
        affiliate_code = str(uuid.uuid4())[:8]
        await db.affiliates.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "affiliate_code": affiliate_code,
            "total_earnings": 0.0,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    else:
        await db.affiliates.delete_one({"user_id": user_id})
    
    return {"message": f"Affiliate status {'enabled' if is_affiliate else 'disabled'}"}

@api_router.get("/admin/affiliate/payouts")
async def admin_get_payout_requests(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    payouts = await db.payout_requests.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return payouts

@api_router.put("/admin/affiliate/payouts/{payout_id}/approve")
async def admin_approve_payout(payout_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.payout_requests.update_one({"id": payout_id}, {"$set": {"status": "approved"}})
    return {"message": "Payout approved"}

# ============================================
# SPRINT 2: MODERATION & ANALYTICS ENDPOINTS
# ============================================

# ENHANCED USER MANAGEMENT
@api_router.get("/admin/users/filter")
async def admin_filter_users(account_type: str = None, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = {}
    if account_type:
        query["account_type"] = account_type
    
    users = await db.users.find(query, {"_id": 0, "password": 0}).to_list(200)
    return users

@api_router.put("/admin/users/{user_id}/verify")
async def admin_verify_user(user_id: str, data: Dict[str, bool], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    is_verified = data.get("is_verified", False)
    await db.users.update_one({"id": user_id}, {"$set": {"verified": is_verified, "verified_at": datetime.now(timezone.utc).isoformat()}})
    return {"message": f"User {'verified' if is_verified else 'unverified'}"}

@api_router.get("/admin/analytics/users")
async def admin_user_analytics(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    personal_users = await db.users.count_documents({"account_type": "personal"})
    business_users = await db.users.count_documents({"account_type": "business"})
    
    return {
        "personal": personal_users,
        "business": business_users,
        "total": personal_users + business_users
    }

# LOTS AUCTION MODERATION
@api_router.get("/admin/lots/pending")
async def admin_get_pending_lots(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    lots = await db.multi_item_listings.find({"status": "pending"}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return lots

@api_router.put("/admin/lots/{lot_id}/moderate")
async def admin_moderate_lot(lot_id: str, data: Dict[str, str], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    action = data.get("action")
    if action == "approve":
        await db.multi_item_listings.update_one({"id": lot_id}, {"$set": {"status": "active"}})
    elif action == "reject":
        await db.multi_item_listings.update_one({"id": lot_id}, {"$set": {"status": "rejected"}})
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    return {"message": f"Lot {action}d successfully"}

# REPORT ENHANCEMENTS
@api_router.put("/admin/reports/{report_id}/update")
async def admin_update_report(report_id: str, data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    update_data = {}
    if "status" in data:
        update_data["status"] = data["status"]
    if "admin_notes" in data:
        update_data["admin_notes"] = data["admin_notes"]
    if "assigned_to" in data:
        update_data["assigned_to"] = data["assigned_to"]
    if "resolution" in data:
        update_data["resolution"] = data["resolution"]
    
    await db.reports.update_one({"id": report_id}, {"$set": update_data})
    return {"message": "Report updated"}

@api_router.get("/admin/reports/filter")
async def admin_filter_reports(category: str = None, severity: str = None, status: str = None, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = {}
    if category:
        query["category"] = category
    if severity:
        query["severity"] = severity
    if status:
        query["status"] = status
    
    reports = await db.reports.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return reports

# ADVANCED ANALYTICS
@api_router.get("/admin/analytics/revenue")
async def admin_revenue_analytics(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get transactions from last 30 days grouped by date
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    transactions = await db.payment_transactions.find(
        {"payment_status": "paid", "created_at": {"$gte": thirty_days_ago.isoformat()}},
        {"_id": 0, "amount": 1, "created_at": 1}
    ).to_list(1000)
    
    # Group by date
    daily_revenue = {}
    for tx in transactions:
        date = tx["created_at"][:10]
        daily_revenue[date] = daily_revenue.get(date, 0) + tx.get("amount", 0)
    
    return [{"date": date, "revenue": revenue} for date, revenue in sorted(daily_revenue.items())]

@api_router.get("/admin/analytics/listings")
async def admin_listing_analytics(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    active = await db.listings.count_documents({"status": "active"})
    sold = await db.listings.count_documents({"status": "sold"})
    pending = await db.listings.count_documents({"status": "pending"})
    cancelled = await db.listings.count_documents({"status": "cancelled"})
    
    return {
        "active": active,
        "sold": sold,
        "pending": pending,
        "cancelled": cancelled
    }

# ============================================
# SPRINT 3: ADVANCED FEATURES ENDPOINTS
# ============================================

# MESSAGING OVERSIGHT
@api_router.get("/admin/messages/flagged")
async def admin_get_flagged_messages(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    messages = await db.messages.find({"flagged": True}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return messages

@api_router.delete("/admin/messages/{message_id}")
async def admin_delete_message(message_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.messages.delete_one({"id": message_id})
    return {"message": "Message deleted"}

@api_router.put("/admin/users/{user_id}/messaging")
async def admin_suspend_messaging(user_id: str, data: Dict[str, bool], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    messaging_suspended = data.get("suspended", False)
    await db.users.update_one({"id": user_id}, {"$set": {"messaging_suspended": messaging_suspended}})
    return {"message": f"Messaging {'suspended' if messaging_suspended else 'restored'}"}

# ADMIN ACTION LOGS
@api_router.post("/admin/logs")
async def admin_create_log(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    log = {
        "id": str(uuid.uuid4()),
        "admin_id": current_user.id,
        "admin_email": current_user.email,
        "action": data.get("action"),
        "target_type": data.get("target_type"),
        "target_id": data.get("target_id"),
        "details": data.get("details", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.admin_logs.insert_one(log)
    return log

@api_router.get("/admin/logs")
async def admin_get_logs(action_type: str = None, limit: int = 100, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = {}
    if action_type:
        query["action"] = action_type
    
    logs = await db.admin_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return logs

# PLATFORM ANNOUNCEMENTS
@api_router.get("/admin/announcements")
async def admin_get_announcements(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    announcements = await db.announcements.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return announcements

@api_router.post("/admin/announcements")
async def admin_create_announcement(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    announcement = {
        "id": str(uuid.uuid4()),
        "title": data.get("title"),
        "message": data.get("message"),
        "target_audience": data.get("target_audience", "all"),
        "status": "active",
        "scheduled_for": data.get("scheduled_for"),
        "created_by": current_user.id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.announcements.insert_one(announcement)
    return announcement

@api_router.delete("/admin/announcements/{announcement_id}")
async def admin_delete_announcement(announcement_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.announcements.delete_one({"id": announcement_id})
    return {"message": "Announcement deleted"}

# ============================================
# TRUST & SAFETY SYSTEM - AI POWERED
# ============================================

# PHASE 1: TRUST SCORING & FRAUD DETECTION

async def calculate_trust_score(user_id: str) -> int:
    """Calculate user trust score (0-100)"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        return 0
    
    score = 50  # Base score
    
    # Account age bonus (max +15)
    if user.get("created_at"):
        account_age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(user["created_at"])).days
        score += min(15, account_age_days // 10)
    
    # Verification bonuses
    if user.get("email_verified"):
        score += 10
    if user.get("phone_verified"):
        score += 10
    
    # Transaction history bonus (max +20)
    transactions = await db.payment_transactions.count_documents({"user_id": user_id, "payment_status": "paid"})
    score += min(20, transactions * 2)
    
    # Report penalties
    reports_against = await db.reports.count_documents({"reported_user_id": user_id})
    score -= reports_against * 5
    
    # Completion rate bonus
    completed = await db.listings.count_documents({"seller_id": user_id, "status": "sold"})
    cancelled = await db.listings.count_documents({"seller_id": user_id, "status": "cancelled"})
    if completed + cancelled > 0:
        completion_rate = completed / (completed + cancelled)
        score += int(completion_rate * 10)
    
    return max(0, min(100, score))

@api_router.get("/admin/trust-safety/scores")
async def get_trust_scores(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    users = await db.users.find({}, {"_id": 0, "password": 0}).to_list(100)
    
    scores = []
    for user in users:
        trust_score = await calculate_trust_score(user["id"])
        scores.append({
            "user_id": user["id"],
            "name": user.get("name"),
            "email": user.get("email"),
            "trust_score": trust_score,
            "risk_level": "high" if trust_score < 40 else "medium" if trust_score < 70 else "low"
        })
    
    return sorted(scores, key=lambda x: x["trust_score"])

@api_router.get("/admin/trust-safety/fraud-flags")
async def get_fraud_flags(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    flags = []
    
    # Duplicate listings detection
    listings = await db.listings.find({"status": "active"}, {"_id": 0}).to_list(1000)
    titles_seen = {}
    for listing in listings:
        title = listing.get("title", "").lower()
        if title in titles_seen:
            flags.append({
                "type": "duplicate_listing",
                "severity": "medium",
                "listing_id": listing["id"],
                "title": listing["title"],
                "description": f"Duplicate of listing {titles_seen[title]}",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        else:
            titles_seen[title] = listing["id"]
    
    # Suspicious pricing detection
    for listing in listings:
        if listing.get("starting_price", 0) > 10000:
            flags.append({
                "type": "suspicious_pricing",
                "severity": "high",
                "listing_id": listing["id"],
                "title": listing["title"],
                "description": f"Unusually high price: ${listing['starting_price']}",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
    
    # High-value bids from new accounts
    bids = await db.bids.find({}, {"_id": 0}).to_list(1000)
    for bid in bids:
        user = await db.users.find_one({"id": bid.get("bidder_id")})
        if user:
            account_age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(user["created_at"])).days
            if account_age_days < 7 and bid.get("amount", 0) > 500:
                flags.append({
                    "type": "new_account_high_bid",
                    "severity": "high",
                    "user_id": user["id"],
                    "user_name": user.get("name"),
                    "bid_amount": bid["amount"],
                    "account_age_days": account_age_days,
                    "description": f"New account ({account_age_days}d old) bidding ${bid['amount']}",
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
    
    return flags

@api_router.get("/admin/trust-safety/collusion-patterns")
async def detect_collusion(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    patterns = []
    
    # Find buyer-seller pairs with multiple cancelled transactions
    cancelled_listings = await db.listings.find({"status": "cancelled"}, {"_id": 0}).to_list(1000)
    
    pair_counts = {}
    for listing in cancelled_listings:
        # Get winning bid if any
        bids = await db.bids.find({"listing_id": listing["id"]}, {"_id": 0}).sort("amount", -1).limit(1).to_list(1)
        if bids:
            pair = f"{listing['seller_id']}-{bids[0].get('bidder_id')}"
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
    
    # Flag pairs with 3+ cancellations
    for pair, count in pair_counts.items():
        if count >= 3:
            seller_id, buyer_id = pair.split("-")
            seller = await db.users.find_one({"id": seller_id})
            buyer = await db.users.find_one({"id": buyer_id})
            
            patterns.append({
                "type": "repeated_cancellations",
                "severity": "high",
                "seller_id": seller_id,
                "seller_name": seller.get("name") if seller else "Unknown",
                "buyer_id": buyer_id,
                "buyer_name": buyer.get("name") if buyer else "Unknown",
                "cancellation_count": count,
                "description": f"{count} cancelled transactions between same buyer-seller pair",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
    
    return patterns

@api_router.post("/admin/trust-safety/verify-requirement")
async def enforce_verification_requirement(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    requirement_type = data.get("type")  # "email" or "phone"
    enabled = data.get("enabled", True)
    
    await db.platform_settings.update_one(
        {"setting_key": f"require_{requirement_type}_verification"},
        {"$set": {"value": enabled, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    
    return {"message": f"{requirement_type.capitalize()} verification requirement {'enabled' if enabled else 'disabled'}"}

# PHASE 2: AI INTEGRATION

EMERGENT_LLM_KEY = "sk-emergent-45818088307Fa1bB23"

@api_router.post("/admin/trust-safety/analyze-content")
async def analyze_content_ai(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    content = data.get("content")
    content_type = data.get("type", "text")  # "text" or "image"
    
    try:
        from emergentintegrations.openai import OpenAIChatIntegration
        
        openai_client = OpenAIChatIntegration(api_key=EMERGENT_LLM_KEY)
        
        prompt = f"""Analyze this content for scams, fraud, or policy violations.
        
Content: {content}

Provide a risk assessment with:
1. Risk Level (low/medium/high)
2. Detected Issues (list)
3. Recommended Action
4. Confidence Score (0-100)

Respond in JSON format."""

        response = openai_client.chat_completion(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        analysis = response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        
        return {
            "analysis": analysis,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"AI analysis error: {str(e)}")
        return {
            "error": str(e),
            "analysis": "AI analysis unavailable"
        }

@api_router.post("/admin/trust-safety/scan-listing")
async def scan_listing_ai(listing_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    try:
        from emergentintegrations.openai import OpenAIChatIntegration
        
        openai_client = OpenAIChatIntegration(api_key=EMERGENT_LLM_KEY)
        
        content_to_analyze = f"Title: {listing.get('title')}\nDescription: {listing.get('description')}\nPrice: ${listing.get('starting_price')}"
        
        prompt = f"""Analyze this auction listing for fraud indicators:

{content_to_analyze}

Check for:
- Scam keywords
- Unrealistic pricing
- Stolen/duplicate content indicators
- Off-platform contact attempts
- Too-good-to-be-true offers

Provide risk assessment in JSON format with risk_level, issues, and recommendations."""

        response = openai_client.chat_completion(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        analysis = response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        
        # Store analysis result
        await db.listing_scans.insert_one({
            "id": str(uuid.uuid4()),
            "listing_id": listing_id,
            "analysis": analysis,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "scanned_by": current_user.id
        })
        
        return {
            "listing_id": listing_id,
            "analysis": analysis,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Listing scan error: {str(e)}")
        return {"error": str(e)}

@api_router.post("/admin/trust-safety/scan-messages")
async def scan_messages_ai(conversation_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    messages = await db.messages.find({"conversation_id": conversation_id}, {"_id": 0}).to_list(100)
    
    scam_keywords = ["whatsapp", "telegram", "crypto", "send money", "wire transfer", "gift card", "outside platform", "direct payment"]
    
    flagged_messages = []
    for msg in messages:
        content_lower = msg.get("content", "").lower()
        found_keywords = [kw for kw in scam_keywords if kw in content_lower]
        
        if found_keywords:
            flagged_messages.append({
                "message_id": msg["id"],
                "content": msg["content"],
                "keywords_found": found_keywords,
                "sender_id": msg.get("sender_id"),
                "severity": "high" if len(found_keywords) > 2 else "medium"
            })
            
            # Auto-flag the message
            await db.messages.update_one({"id": msg["id"]}, {"$set": {"flagged": True, "flagged_reason": f"Scam keywords: {', '.join(found_keywords)}"}})
    
    return {
        "conversation_id": conversation_id,
        "flagged_count": len(flagged_messages),
        "flagged_messages": flagged_messages
    }

# PHASE 3: ADVANCED BEHAVIORAL ANALYSIS

@api_router.get("/admin/trust-safety/behavioral-analysis")
async def behavioral_analysis(user_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Analyze bidding patterns
    bids = await db.bids.find({"bidder_id": user_id}, {"_id": 0}).to_list(1000)
    bid_amounts = [b.get("amount", 0) for b in bids]
    avg_bid = sum(bid_amounts) / len(bid_amounts) if bid_amounts else 0
    
    # Analyze messaging patterns
    messages_sent = await db.messages.count_documents({"sender_id": user_id})
    flagged_messages = await db.messages.count_documents({"sender_id": user_id, "flagged": True})
    
    # Analyze transaction patterns
    completed_transactions = await db.payment_transactions.count_documents({"user_id": user_id, "payment_status": "paid"})
    failed_transactions = await db.payment_transactions.count_documents({"user_id": user_id, "payment_status": "failed"})
    
    # Calculate risk indicators
    risk_indicators = []
    if flagged_messages > 0:
        risk_indicators.append(f"{flagged_messages} flagged messages")
    if failed_transactions > completed_transactions:
        risk_indicators.append("More failed than completed transactions")
    if len(bids) > 20 and completed_transactions == 0:
        risk_indicators.append("Many bids but no completed purchases")
    
    behavior_score = 100
    behavior_score -= flagged_messages * 15
    behavior_score -= (failed_transactions * 5)
    behavior_score = max(0, behavior_score)
    
    return {
        "user_id": user_id,
        "name": user.get("name"),
        "behavior_score": behavior_score,
        "risk_level": "high" if behavior_score < 40 else "medium" if behavior_score < 70 else "low",
        "statistics": {
            "total_bids": len(bids),
            "average_bid": avg_bid,
            "messages_sent": messages_sent,
            "flagged_messages": flagged_messages,
            "completed_transactions": completed_transactions,
            "failed_transactions": failed_transactions
        },
        "risk_indicators": risk_indicators,
        "recommended_actions": [
            "Suspend messaging" if flagged_messages > 2 else None,
            "Require re-verification" if behavior_score < 50 else None,
            "Manual review required" if len(risk_indicators) > 2 else None
        ]
    }

@api_router.post("/admin/trust-safety/auto-action")
async def execute_auto_action(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user_id = data.get("user_id")
    action = data.get("action")  # "suspend_messaging", "require_verification", "suspend_account"
    reason = data.get("reason", "Automated safety action")
    
    if action == "suspend_messaging":
        await db.users.update_one({"id": user_id}, {"$set": {"messaging_suspended": True, "suspension_reason": reason}})
    elif action == "require_verification":
        await db.users.update_one({"id": user_id}, {"$set": {"email_verified": False, "phone_verified": False, "verification_required": True}})
    elif action == "suspend_account":
        await db.users.update_one({"id": user_id}, {"$set": {"status": "suspended", "suspension_reason": reason}})
    
    # Log the action
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()),
        "admin_id": "SYSTEM_AUTO",
        "admin_email": "system@bazario.com",
        "action": f"auto_{action}",
        "target_type": "user",
        "target_id": user_id,
        "details": reason,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"message": f"Auto-action '{action}' executed for user {user_id}"}

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
    listing_id = data.get("listing_id")
    if not listing_id:
        raise HTTPException(status_code=400, detail="listing_id is required")
    
    # Verify listing exists and belongs to user
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    if listing["seller_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to promote this listing")
    
    promotion_id = str(uuid.uuid4())
    current_time = datetime.now(timezone.utc).isoformat()
    
    promotion_doc = {
        "id": promotion_id,
        "listing_id": listing_id,
        "seller_id": current_user.id,
        "promotion_type": data.get("promotion_type"),
        "price": data.get("price"),
        "start_date": current_time,
        "end_date": data.get("end_date"),
        "targeting": data.get("targeting", {}),
        "impressions": 0,
        "clicks": 0,
        "status": "pending",
        "payment_status": "pending",
        "created_at": current_time
    }
    
    await db.promotions.insert_one(promotion_doc)
    
    # Return a clean response without MongoDB fields
    return {
        "id": promotion_id,
        "listing_id": listing_id,
        "seller_id": current_user.id,
        "promotion_type": data.get("promotion_type"),
        "price": data.get("price"),
        "start_date": current_time,
        "end_date": data.get("end_date"),
        "targeting": data.get("targeting", {}),
        "impressions": 0,
        "clicks": 0,
        "status": "pending",
        "payment_status": "pending",
        "created_at": current_time
    }

@api_router.get("/promotions/my")
async def get_my_promotions(current_user: User = Depends(get_current_user)):
    promotions = await db.promotions.find(
        {"seller_id": current_user.id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return promotions


# Watchlist Endpoints
@api_router.post("/watchlist/add")
async def add_to_watchlist(listing_id: str, current_user: User = Depends(get_current_user)):
    """Add a listing to user's watchlist"""
    try:
        # Check if listing exists
        listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")
        
        # Check if already in watchlist
        existing = await db.watchlist.find_one({
            "user_id": current_user.id,
            "listing_id": listing_id
        })
        
        if existing:
            return {"message": "Already in watchlist", "already_added": True}
        
        # Add to watchlist
        watchlist_item = {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "listing_id": listing_id,
            "added_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.watchlist.insert_one(watchlist_item)
        return {"message": "Added to watchlist", "success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding to watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to add to watchlist")

@api_router.post("/watchlist/remove")
async def remove_from_watchlist(listing_id: str, current_user: User = Depends(get_current_user)):
    """Remove a listing from user's watchlist"""
    try:
        result = await db.watchlist.delete_one({
            "user_id": current_user.id,
            "listing_id": listing_id
        })
        
        if result.deleted_count == 0:
            return {"message": "Item not in watchlist", "success": False}
        
        return {"message": "Removed from watchlist", "success": True}
        
    except Exception as e:
        logger.error(f"Error removing from watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to remove from watchlist")

@api_router.get("/watchlist")
async def get_watchlist(current_user: User = Depends(get_current_user)):
    """Get user's watchlist with listing details"""
    try:
        # Get all watchlist items for user
        watchlist_items = await db.watchlist.find(
            {"user_id": current_user.id},
            {"_id": 0}
        ).sort("added_at", -1).to_list(100)
        
        if not watchlist_items:
            return []
        
        # Get listing IDs
        listing_ids = [item["listing_id"] for item in watchlist_items]
        
        # Fetch listing details
        listings = await db.listings.find(
            {"id": {"$in": listing_ids}, "status": {"$ne": "deleted"}},
            {"_id": 0}
        ).to_list(100)
        
        # Create a map of listing_id to listing for quick lookup
        listings_map = {listing["id"]: listing for listing in listings}
        
        # Combine watchlist items with listing details
        result = []
        for item in watchlist_items:
            listing = listings_map.get(item["listing_id"])
            if listing:
                result.append({
                    **listing,
                    "watchlist_added_at": item["added_at"]
                })
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch watchlist")

@api_router.get("/watchlist/check/{listing_id}")
async def check_watchlist_status(listing_id: str, current_user: User = Depends(get_current_user)):
    """Check if a listing is in user's watchlist"""
    try:
        exists = await db.watchlist.find_one({
            "user_id": current_user.id,
            "listing_id": listing_id
        })
        
        return {"in_watchlist": exists is not None}
        
    except Exception as e:
        logger.error(f"Error checking watchlist status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check watchlist status")


# Recently Viewed Tracking Endpoints
@api_router.post("/tracking/view/{listing_id}")
async def track_listing_view(listing_id: str, current_user: User = Depends(get_current_user)):
    """Track a listing view for logged-in users"""
    try:
        # Check if listing exists
        listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")
        
        # Check if already viewed recently (within last 24 hours)
        recent_view = await db.recently_viewed.find_one({
            "user_id": current_user.id,
            "listing_id": listing_id
        })
        
        current_time = datetime.now(timezone.utc).isoformat()
        
        if recent_view:
            # Update timestamp
            await db.recently_viewed.update_one(
                {"user_id": current_user.id, "listing_id": listing_id},
                {"$set": {"viewed_at": current_time}}
            )
        else:
            # Add new view record
            view_record = {
                "id": str(uuid.uuid4()),
                "user_id": current_user.id,
                "listing_id": listing_id,
                "viewed_at": current_time
            }
            await db.recently_viewed.insert_one(view_record)
        
        return {"message": "View tracked", "success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking view: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to track view")

@api_router.get("/tracking/recently-viewed")
async def get_recently_viewed(limit: int = 10, current_user: User = Depends(get_current_user)):
    """Get user's recently viewed listings"""
    try:
        # Get recently viewed records
        viewed_records = await db.recently_viewed.find(
            {"user_id": current_user.id},
            {"_id": 0}
        ).sort("viewed_at", -1).limit(limit).to_list(limit)
        
        if not viewed_records:
            return []
        
        # Get listing IDs
        listing_ids = [record["listing_id"] for record in viewed_records]
        
        # Fetch listing details
        listings = await db.listings.find(
            {"id": {"$in": listing_ids}, "status": {"$ne": "deleted"}},
            {"_id": 0}
        ).to_list(limit)
        
        # Create a map for quick lookup
        listings_map = {listing["id"]: listing for listing in listings}
        
        # Return listings in the order they were viewed
        result = []
        for record in viewed_records:
            listing = listings_map.get(record["listing_id"])
            if listing:
                result.append({
                    **listing,
                    "viewed_at": record["viewed_at"]
                })
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching recently viewed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch recently viewed")

# Carousel Data Endpoints
@api_router.get("/carousel/ending-soon")
async def get_ending_soon_listings(limit: int = 12):
    """Get listings ending soon (within next 24 hours)"""
    try:
        current_time = datetime.now(timezone.utc)
        twenty_four_hours_later = current_time + timedelta(hours=24)
        
        listings = await db.listings.find(
            {
                "status": "active",
                "auction_end_date": {
                    "$gte": current_time.isoformat(),
                    "$lte": twenty_four_hours_later.isoformat()
                }
            },
            {"_id": 0}
        ).sort("auction_end_date", 1).limit(limit).to_list(limit)
        
        return listings
        
    except Exception as e:
        logger.error(f"Error fetching ending soon listings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch ending soon listings")

@api_router.get("/carousel/featured")
async def get_featured_listings(limit: int = 12):
    """Get featured/promoted listings"""
    try:
        listings = await db.listings.find(
            {
                "status": "active",
                "is_promoted": True
            },
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        return listings
        
    except Exception as e:
        logger.error(f"Error fetching featured listings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch featured listings")


@api_router.get("/carousel/new-listings")
async def get_new_listings(limit: int = 12):
    """Get newest listings (created in last 7 days)"""
    try:
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        
        listings = await db.listings.find(
            {
                "status": "active",
                "created_at": {"$gte": seven_days_ago.isoformat()}
            },
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        return listings
        
    except Exception as e:
        logger.error(f"Error fetching new listings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch new listings")

@api_router.get("/carousel/recently-sold")
async def get_recently_sold(limit: int = 12):
    """Get recently sold items"""
    try:
        listings = await db.listings.find(
            {
                "status": "sold"
            },
            {"_id": 0}
        ).sort("sold_at", -1).limit(limit).to_list(limit)
        
        return listings
        
    except Exception as e:
        logger.error(f"Error fetching recently sold: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch recently sold")

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

# ==================== INVOICE GENERATION ====================

from weasyprint import HTML
from invoice_templates import lots_won_template
import os

async def generate_paddle_number(auction_id: str) -> int:
    """Generate next paddle number for auction (starts at 5051)"""
    # Find highest paddle number for this auction
    highest = await db.paddle_numbers.find(
        {"auction_id": auction_id}
    ).sort("paddle_number", -1).limit(1).to_list(1)
    
    if highest:
        return highest[0]["paddle_number"] + 1
    return 5051  # Starting paddle number

async def generate_invoice_number(auction_id: str) -> str:
    """Generate invoice number: BV-{year}-{auction_id_short}-{sequence}"""
    year = datetime.now().year
    auction_short = auction_id[:8]  # First 8 chars of UUID
    
    # Count existing invoices for this auction
    count = await db.invoices.count_documents({"auction_id": auction_id})
    sequence = count + 1
    
    return f"BV-{year}-{auction_short}-{sequence:04d}"

@api_router.post("/invoices/lots-won/{auction_id}/{user_id}")
async def generate_lots_won_invoice(
    auction_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Generate Buyer Lots Won Summary PDF
    Requires admin privileges or matching user_id
    """
    # Check permissions (admin or own invoice)
    if current_user.account_type != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Fetch auction
    auction = await db.multi_item_listings.find_one({"id": auction_id})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    # Fetch buyer
    buyer = await db.users.find_one({"id": user_id})
    if not buyer:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get or create paddle number
    paddle_record = await db.paddle_numbers.find_one({
        "auction_id": auction_id,
        "user_id": user_id
    })
    
    if not paddle_record:
        paddle_num = await generate_paddle_number(auction_id)
        paddle_record = {
            "id": str(uuid.uuid4()),
            "auction_id": auction_id,
            "user_id": user_id,
            "paddle_number": paddle_num,
            "assigned_at": datetime.now(timezone.utc).isoformat()
        }
        await db.paddle_numbers.insert_one(paddle_record)
    
    # Find lots won by this buyer
    # For MVP, we'll use lots from the auction that have bids from this user
    # In production, you'd track winning bids
    
    # For demo purposes, let's use first 3 lots as "won"
    lots_won = []
    for lot in auction['lots'][:3]:  # Demo: first 3 lots
        lots_won.append({
            "lot_number": lot['lot_number'],
            "title": lot['title'],
            "description": lot['description'],
            "quantity": lot['quantity'],
            "hammer_price": lot['current_price']  # Use current_price as hammer price
        })
    
    if not lots_won:
        raise HTTPException(status_code=400, detail="No lots won by this buyer")
    
    # Generate invoice number
    invoice_number = await generate_invoice_number(auction_id)
    
    # Prepare data for template
    template_data = {
        "invoice_number": invoice_number,
        "buyer": {
            "name": buyer['name'],
            "company_name": buyer.get('company_name'),
            "billing_address": buyer.get('billing_address', buyer.get('address')),
            "phone": buyer['phone'],
            "email": buyer['email']
        },
        "paddle_number": paddle_record['paddle_number'],
        "auction": {
            "title": auction['title'],
            "city": auction['city'],
            "region": auction['region'],
            "location": auction.get('location'),
            "auction_end_date": datetime.fromisoformat(auction['auction_end_date']) if isinstance(auction['auction_end_date'], str) else auction['auction_end_date']
        },
        "lots": lots_won,
        "premium_percentage": auction.get('premium_percentage', 5.0),
        "tax_rate_gst": auction.get('tax_rate_gst', 5.0),
        "tax_rate_qst": auction.get('tax_rate_qst', 9.975),
        "payment_deadline": "Within 3 business days"
    }
    
    # Generate HTML
    html_content = lots_won_template(template_data)
    
    # Create user invoice directory
    invoice_dir = Path(f"/app/invoices/{user_id}")
    invoice_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate PDF
    pdf_filename = f"LotsWon_{auction_id}_{int(datetime.now().timestamp())}.pdf"
    pdf_path = invoice_dir / pdf_filename
    
    HTML(string=html_content).write_pdf(pdf_path)
    
    # Save invoice record to database
    invoice_record = {
        "id": str(uuid.uuid4()),
        "invoice_number": invoice_number,
        "invoice_type": "lots_won",
        "user_id": user_id,
        "auction_id": auction_id,
        "pdf_path": str(pdf_path),
        "generated_date": datetime.now(timezone.utc).isoformat(),
        "status": "generated"
    }
    await db.invoices.insert_one(invoice_record)
    
    return {
        "success": True,
        "invoice_number": invoice_number,
        "pdf_path": str(pdf_path),
        "paddle_number": paddle_record['paddle_number'],
        "message": "Invoice generated successfully"
    }

@api_router.get("/invoices/{user_id}")
async def get_user_invoices(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get all invoices for a user"""
    if current_user.account_type != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    invoices = await db.invoices.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    
    for invoice in invoices:
        if isinstance(invoice.get('generated_date'), str):
            invoice['generated_date'] = datetime.fromisoformat(invoice['generated_date'])
    
    return invoices

# ==================== END INVOICE GENERATION ====================

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
