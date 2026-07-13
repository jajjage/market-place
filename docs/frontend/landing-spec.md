# Frontend Landing Page Specification

This document details the brand elements, landing page layout, interactive elements, and performance integration considerations for the web application interface.

---

## 1. Page Structure

1.  **Navigation Bar**: minimal transparent header, logo, page menus, login/signup actions.
2.  **Hero Section**: full-width gradient, main CTAs ("Get Started", "Learn More"), floating statistics cards showing transaction metrics.
3.  **How It Works**: 3-step escrow cards (Secure Payment ➔ Protected Holding ➔ Safe Release).
4.  **Key Features Grid**: Buyer protection, Seller security, Dispute Resolution, Real-time chat.
5.  **Trust & Security**: Verification indicators, fraud guarantees, payment logo partners.
6.  **User Benefits**: Split layout showing value-props for Buyers vs. Sellers.
7.  **Footer**: Quick links, legal policies, social profiles, newsletter form.

---

## 2. API Caching & Optimization Note (Backend N+1 Solutions)

When listing items for the landing page or catalogs, the backend implements the following database optimizations to prevent N+1 queries during loading:

- **Eager Loading**: The product list service evaluates optimized querysets using `select_related` on brand, category, condition, seller, seller profile, and meta.
- **Prefetching Relations**: Prefetches images (`primary_images` and `all_active_images`), product variants, and approved ratings (`approved_ratings`).
- **Annotations**: Annotates the average ratings count, watchers count, and total view counts directly in the SQL query rather than executing Python-level loops.
- **Cache-Key Hashing**: Serializes request filter parameters into an MD5-hashed cache key, caching the evaluated list for maximum response speed.
