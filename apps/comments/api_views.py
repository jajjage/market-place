from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg
from django.utils import timezone
from datetime import timedelta
import logging

from apps.comments.models import UserRating
from apps.comments.services import RatingService

logger = logging.getLogger("ratings_performance")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def rating_analytics_view(request, user_id):
    """Get detailed rating analytics for a user (seller)"""
    start_time = timezone.now()

    # Get rating analytics with time-based breakdowns
    ratings = UserRating.objects.filter(to_user_id=user_id)

    # Time-based analytics
    now = timezone.now()
    last_30_days = now - timedelta(days=30)
    last_90_days = now - timedelta(days=90)
    last_year = now - timedelta(days=365)

    analytics = {
        "overall": {
            "average_rating": ratings.aggregate(avg=Avg("rating"))["avg"] or 0,
            "total_ratings": ratings.count(),
            "distribution": {
                f"{i}_star": ratings.filter(rating=i).count() for i in range(1, 6)
            },
        },
        "trends": {
            "last_30_days": {
                "count": ratings.filter(created_at__gte=last_30_days).count(),
                "average": ratings.filter(created_at__gte=last_30_days).aggregate(
                    avg=Avg("rating")
                )["avg"]
                or 0,
            },
            "last_90_days": {
                "count": ratings.filter(created_at__gte=last_90_days).count(),
                "average": ratings.filter(created_at__gte=last_90_days).aggregate(
                    avg=Avg("rating")
                )["avg"]
                or 0,
            },
            "last_year": {
                "count": ratings.filter(created_at__gte=last_year).count(),
                "average": ratings.filter(created_at__gte=last_year).aggregate(
                    avg=Avg("rating")
                )["avg"]
                or 0,
            },
        },
        "monthly_breakdown": [],
    }

    # Monthly breakdown for the last 12 months
    for i in range(12):
        month_start = now - timedelta(days=30 * (i + 1))
        month_end = now - timedelta(days=30 * i)

        month_data = ratings.filter(
            created_at__gte=month_start, created_at__lt=month_end
        ).aggregate(count=Count("id"), average=Avg("rating"))

        analytics["monthly_breakdown"].append(
            {
                "month": month_start.strftime("%Y-%m"),
                "count": month_data["count"],
                "average": month_data["average"] or 0,
            }
        )

    elapsed = (timezone.now() - start_time).total_seconds() * 1000
    logger.info(f"Generated rating analytics for user {user_id} in {elapsed:.2f}ms")

    return Response(analytics)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def flag_rating_view(request, rating_id):
    """Flag a rating for moderation (only admins or the rated user)"""
    try:
        rating = UserRating.objects.get(id=rating_id)
    except UserRating.DoesNotExist:
        return Response({"error": "Rating not found"}, status=404)

    # Check permissions
    if not (request.user.is_staff or request.user == rating.to_user):
        return Response({"error": "Permission denied"}, status=403)

    reason = request.data.get("reason", "")

    rating.is_flagged = True
    rating.moderation_notes = f"Flagged by {request.user.get_full_name()}: {reason}"
    rating.save()

    logger.info(f"Rating {rating_id} flagged by user {request.user.id}")

    return Response({"message": "Rating flagged for moderation"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def rating_reminders_view(request):
    """Get rating reminders for the authenticated user"""
    pending_ratings = RatingService.get_pending_ratings_for_user(request.user)

    # Categorize by urgency
    urgent = []  # Expires in 3 days or less
    normal = []  # Expires in 4-14 days
    low = []  # Expires in 15+ days

    for rating in pending_ratings:
        days = rating["days_remaining"]
        if days <= 3:
            urgent.append(rating)
        elif days <= 14:
            normal.append(rating)
        else:
            low.append(rating)

    return Response(
        {
            "total_pending": len(pending_ratings),
            "urgent": urgent,
            "normal": normal,
            "low": low,
        }
    )
