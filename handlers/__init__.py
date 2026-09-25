from aiogram import Router

from . import start, booking, my_bookings, reviews, profile, admin


def get_all_routers() -> list[Router]:
    return [
        start.router,
        admin.router,
        reviews.router,
        profile.router,
        booking.router,
        my_bookings.router,
    ]
