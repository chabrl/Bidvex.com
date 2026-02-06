"""
BidVex Vehicle Auction - Seller Document Upload Service
Handles document upload, storage, and verification for sellers
"""

import os
import uuid
import logging
import aiofiles
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)

# Document upload directory
UPLOAD_DIR = Path("/app/uploads/seller_documents")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class DocumentType(str, Enum):
    # Individual seller documents
    IDENTITY_FRONT = "identity_front"
    IDENTITY_BACK = "identity_back"
    PROOF_OF_ADDRESS = "proof_of_address"
    
    # Business seller documents
    BUSINESS_REGISTRATION = "business_registration"
    DEALER_LICENSE = "dealer_license"
    AUCTIONEER_LICENSE = "auctioneer_license"
    INSURANCE_CERTIFICATE = "insurance_certificate"
    TAX_CERTIFICATE = "tax_certificate"
    
    # Vehicle-specific documents
    VEHICLE_OWNERSHIP = "vehicle_ownership"
    VEHICLE_TITLE = "vehicle_title"
    INSPECTION_REPORT = "inspection_report"
    CARFAX_REPORT = "carfax_report"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


# Required documents by seller type
REQUIRED_DOCUMENTS = {
    "private": [
        DocumentType.IDENTITY_FRONT,
        DocumentType.IDENTITY_BACK,
    ],
    "dealer": [
        DocumentType.BUSINESS_REGISTRATION,
        DocumentType.DEALER_LICENSE,
        DocumentType.INSURANCE_CERTIFICATE,
    ],
    "auctioneer": [
        DocumentType.BUSINESS_REGISTRATION,
        DocumentType.AUCTIONEER_LICENSE,
        DocumentType.INSURANCE_CERTIFICATE,
    ]
}

# Allowed file types
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


async def save_uploaded_file(
    file_content: bytes,
    original_filename: str,
    seller_id: str,
    document_type: str
) -> Dict[str, Any]:
    """
    Save uploaded file to storage
    Returns file metadata including storage path
    """
    # Validate file extension
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")
    
    # Validate file size
    if len(file_content) > MAX_FILE_SIZE:
        raise ValueError(f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB")
    
    # Generate unique filename
    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}{ext}"
    
    # Create seller directory
    seller_dir = UPLOAD_DIR / seller_id
    seller_dir.mkdir(exist_ok=True)
    
    # Save file
    file_path = seller_dir / safe_filename
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(file_content)
    
    # Calculate file hash for integrity
    file_hash = hashlib.sha256(file_content).hexdigest()
    
    logger.info(f"Saved document {document_type} for seller {seller_id}: {safe_filename}")
    
    return {
        "file_id": file_id,
        "filename": safe_filename,
        "original_filename": original_filename,
        "file_path": str(file_path),
        "relative_path": f"seller_documents/{seller_id}/{safe_filename}",
        "file_size": len(file_content),
        "file_hash": file_hash,
        "mime_type": get_mime_type(ext)
    }


def get_mime_type(extension: str) -> str:
    """Get MIME type from file extension"""
    mime_types = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp"
    }
    return mime_types.get(extension, "application/octet-stream")


async def create_seller_document(
    db,
    seller_id: str,
    user_id: str,
    document_type: str,
    file_content: bytes,
    original_filename: str,
    description: str = None
) -> Dict[str, Any]:
    """
    Upload and create a seller document record
    """
    # Save file
    file_info = await save_uploaded_file(
        file_content,
        original_filename,
        seller_id,
        document_type
    )
    
    now = datetime.now(timezone.utc)
    
    # Check if document of this type already exists
    existing = await db.seller_documents.find_one({
        "seller_id": seller_id,
        "document_type": document_type,
        "status": {"$ne": DocumentStatus.REJECTED.value}
    })
    
    if existing:
        # Archive old document
        await db.seller_documents.update_one(
            {"id": existing["id"]},
            {"$set": {"archived": True, "archived_at": now}}
        )
    
    # Create document record
    document = {
        "id": file_info["file_id"],
        "seller_id": seller_id,
        "user_id": user_id,
        "document_type": document_type,
        "status": DocumentStatus.PENDING.value,
        
        # File info
        "filename": file_info["filename"],
        "original_filename": file_info["original_filename"],
        "file_path": file_info["file_path"],
        "relative_path": file_info["relative_path"],
        "file_size": file_info["file_size"],
        "file_hash": file_info["file_hash"],
        "mime_type": file_info["mime_type"],
        
        # Metadata
        "description": description,
        "uploaded_at": now,
        "created_at": now,
        "updated_at": None,
        
        # Review info
        "reviewed_by": None,
        "reviewed_at": None,
        "review_notes": None,
        "rejection_reason": None,
        
        # Flags
        "archived": False,
        "expires_at": None
    }
    
    await db.seller_documents.insert_one(document)
    
    # Remove _id for response
    document.pop("_id", None)
    
    # Log audit
    await db.vehicle_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "entity_type": "seller_document",
        "entity_id": document["id"],
        "action": "document_uploaded",
        "performed_by": user_id,
        "performed_by_role": "seller",
        "new_value": {
            "document_type": document_type,
            "filename": original_filename
        },
        "created_at": now
    })
    
    return document


async def get_seller_documents(
    db,
    seller_id: str,
    document_type: str = None,
    status: str = None,
    include_archived: bool = False
) -> List[Dict[str, Any]]:
    """Get all documents for a seller"""
    query = {"seller_id": seller_id}
    
    if document_type:
        query["document_type"] = document_type
    if status:
        query["status"] = status
    if not include_archived:
        query["archived"] = {"$ne": True}
    
    cursor = db.seller_documents.find(query, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(length=100)


async def get_document_by_id(db, document_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific document by ID"""
    return await db.seller_documents.find_one({"id": document_id}, {"_id": 0})


async def approve_document(
    db,
    document_id: str,
    admin_id: str,
    notes: str = None
) -> Dict[str, Any]:
    """Admin: Approve a seller document"""
    document = await db.seller_documents.find_one({"id": document_id})
    if not document:
        raise ValueError("Document not found")
    
    if document.get("status") == DocumentStatus.APPROVED.value:
        raise ValueError("Document already approved")
    
    now = datetime.now(timezone.utc)
    
    await db.seller_documents.update_one(
        {"id": document_id},
        {
            "$set": {
                "status": DocumentStatus.APPROVED.value,
                "reviewed_by": admin_id,
                "reviewed_at": now,
                "review_notes": notes,
                "updated_at": now
            }
        }
    )
    
    # Log audit
    await db.vehicle_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "entity_type": "seller_document",
        "entity_id": document_id,
        "action": "document_approved",
        "performed_by": admin_id,
        "performed_by_role": "admin",
        "previous_value": {"status": document.get("status")},
        "new_value": {"status": DocumentStatus.APPROVED.value, "notes": notes},
        "created_at": now
    })
    
    # Send email notification to user
    try:
        user = await db.users.find_one({"id": document.get("user_id")})
        if user and user.get("email"):
            from services.email_notifications import send_document_approved_email
            await send_document_approved_email(
                user_email=user["email"],
                user_name=user.get("full_name", user.get("email")),
                document_type=document.get("document_type")
            )
            logger.info(f"Sent document approval email to {user['email']}")
    except Exception as e:
        logger.error(f"Failed to send document approval email: {e}")
    
    # Check if all required documents are approved
    await check_seller_verification_status(db, document["seller_id"])
    
    return await get_document_by_id(db, document_id)


async def reject_document(
    db,
    document_id: str,
    admin_id: str,
    reason: str
) -> Dict[str, Any]:
    """Admin: Reject a seller document"""
    document = await db.seller_documents.find_one({"id": document_id})
    if not document:
        raise ValueError("Document not found")
    
    now = datetime.now(timezone.utc)
    
    await db.seller_documents.update_one(
        {"id": document_id},
        {
            "$set": {
                "status": DocumentStatus.REJECTED.value,
                "reviewed_by": admin_id,
                "reviewed_at": now,
                "rejection_reason": reason,
                "updated_at": now
            }
        }
    )
    
    # Log audit
    await db.vehicle_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "entity_type": "seller_document",
        "entity_id": document_id,
        "action": "document_rejected",
        "performed_by": admin_id,
        "performed_by_role": "admin",
        "previous_value": {"status": document.get("status")},
        "new_value": {"status": DocumentStatus.REJECTED.value, "reason": reason},
        "created_at": now
    })
    
    # Send email notification to user
    try:
        user = await db.users.find_one({"id": document.get("user_id")})
        if user and user.get("email"):
            from services.email_notifications import send_document_rejected_email
            await send_document_rejected_email(
                user_email=user["email"],
                user_name=user.get("full_name", user.get("email")),
                document_type=document.get("document_type"),
                rejection_reason=reason
            )
            logger.info(f"Sent document rejection email to {user['email']}")
    except Exception as e:
        logger.error(f"Failed to send document rejection email: {e}")
    
    return await get_document_by_id(db, document_id)


async def check_seller_verification_status(db, seller_id: str) -> Dict[str, Any]:
    """
    Check if seller has all required documents approved
    Auto-approve seller if all documents are verified
    """
    seller = await db.vehicle_sellers.find_one({"id": seller_id})
    if not seller:
        return {"status": "not_found"}
    
    seller_type = seller.get("seller_type", "private")
    required_docs = REQUIRED_DOCUMENTS.get(seller_type, [])
    
    # Get all approved documents
    approved_docs = await db.seller_documents.find({
        "seller_id": seller_id,
        "status": DocumentStatus.APPROVED.value,
        "archived": {"$ne": True}
    }).to_list(length=100)
    
    approved_types = {doc["document_type"] for doc in approved_docs}
    required_types = {doc.value for doc in required_docs}
    
    missing_docs = required_types - approved_types
    all_verified = len(missing_docs) == 0
    
    # Update seller verification status
    now = datetime.now(timezone.utc)
    
    if all_verified and seller.get("verification_status") != "approved":
        await db.vehicle_sellers.update_one(
            {"id": seller_id},
            {
                "$set": {
                    "documents_verified": True,
                    "documents_verified_at": now,
                    "updated_at": now
                }
            }
        )
        
        logger.info(f"Seller {seller_id} documents fully verified")
        
        # Send seller approval email notification
        try:
            user = await db.users.find_one({"id": seller.get("user_id")})
            if user and user.get("email"):
                from services.email_notifications import send_seller_approved_email
                await send_seller_approved_email(
                    user_email=user["email"],
                    user_name=user.get("full_name", user.get("email")),
                    seller_type=seller_type
                )
                logger.info(f"Sent seller approval email to {user['email']}")
        except Exception as e:
            logger.error(f"Failed to send seller approval email: {e}")
    
    return {
        "seller_id": seller_id,
        "seller_type": seller_type,
        "required_documents": list(required_types),
        "approved_documents": list(approved_types),
        "missing_documents": list(missing_docs),
        "all_verified": all_verified
    }


async def get_pending_documents_for_admin(db, limit: int = 50) -> List[Dict[str, Any]]:
    """Admin: Get all pending documents for review"""
    pipeline = [
        {"$match": {"status": DocumentStatus.PENDING.value, "archived": {"$ne": True}}},
        {"$sort": {"created_at": 1}},
        {"$limit": limit},
        {"$lookup": {
            "from": "vehicle_sellers",
            "localField": "seller_id",
            "foreignField": "id",
            "as": "seller"
        }},
        {"$unwind": {"path": "$seller", "preserveNullAndEmptyArrays": True}},
        {"$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "id",
            "as": "user"
        }},
        {"$unwind": {"path": "$user", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "id": 1,
            "seller_id": 1,
            "document_type": 1,
            "original_filename": 1,
            "file_size": 1,
            "mime_type": 1,
            "status": 1,
            "uploaded_at": 1,
            "seller_name": {"$ifNull": ["$seller.business_name", "$user.full_name"]},
            "seller_type": "$seller.seller_type",
            "seller_email": "$user.email"
        }}
    ]
    
    cursor = db.seller_documents.aggregate(pipeline)
    return await cursor.to_list(length=limit)


async def get_document_file(document_id: str) -> Optional[bytes]:
    """Get document file content by ID"""
    # Find document to get file path
    # This would be called after verifying access permissions
    file_path = UPLOAD_DIR / "**" / f"{document_id}.*"
    
    import glob
    matches = glob.glob(str(file_path), recursive=True)
    
    if not matches:
        return None
    
    async with aiofiles.open(matches[0], "rb") as f:
        return await f.read()


# Export document types for API
def get_document_types_for_seller_type(seller_type: str) -> List[Dict[str, Any]]:
    """Get required document types for a seller type"""
    required = REQUIRED_DOCUMENTS.get(seller_type, [])
    
    return [
        {
            "type": doc.value,
            "name": doc.value.replace("_", " ").title(),
            "required": True,
            "description": get_document_description(doc)
        }
        for doc in required
    ]


def get_document_description(doc_type: DocumentType) -> str:
    """Get human-readable description for document type"""
    descriptions = {
        DocumentType.IDENTITY_FRONT: "Front of government-issued ID (driver's license, passport)",
        DocumentType.IDENTITY_BACK: "Back of government-issued ID",
        DocumentType.PROOF_OF_ADDRESS: "Utility bill or bank statement (less than 3 months old)",
        DocumentType.BUSINESS_REGISTRATION: "Official business registration certificate",
        DocumentType.DEALER_LICENSE: "Valid dealer license from provincial authority",
        DocumentType.AUCTIONEER_LICENSE: "Valid auctioneer license",
        DocumentType.INSURANCE_CERTIFICATE: "Current business liability insurance certificate",
        DocumentType.TAX_CERTIFICATE: "GST/HST registration certificate",
        DocumentType.VEHICLE_OWNERSHIP: "Vehicle ownership/registration document",
        DocumentType.VEHICLE_TITLE: "Clear vehicle title",
        DocumentType.INSPECTION_REPORT: "Recent mechanical inspection report",
        DocumentType.CARFAX_REPORT: "CARFAX or equivalent vehicle history report"
    }
    return descriptions.get(doc_type, "Supporting document")
