# Kibana Dashboard Setup Guide

This document describes how to access Kibana, configure data views (index patterns) for the SafeTrade search indices, and build a dashboard to inspect indexed product data.

---

## 1. Accessing Kibana

In the local environment configured in [docker-compose.yml](file:///c:/Users/musta/fasu-marketplace/market-place/docker-compose.yml), Kibana is running alongside Elasticsearch.

*   **URL:** `http://localhost:5601`
*   **Security:** Authentication is disabled in development mode (`xpack.security.enabled=false`), so you will not need a username or password.

---

## 2. Creating Data Views (Index Patterns)

Before you can visualize or search documents in Kibana, you must create a **Data View** to tell Kibana which indices to read.

### A. Create Data View for Products
1. Open your browser and navigate to `http://localhost:5601`.
2. Open the main menu on the left (three lines icon) and go to **Management** ➔ **Stack Management**.
3. In the left sidebar under the *Kibana* section, click **Data Views**.
4. Click the **Create data view** button in the top right.
5. Configure the following settings:
    *   **Name:** `products`
    *   **Index pattern:** `products`
    *   **Timestamp field:** `created_at`
6. Click **Save data view to Kibana**.

### B. Create Data View for Brands
1. In the same **Data Views** settings tab, click **Create data view** again.
2. Configure the following settings:
    *   **Name:** `brands`
    *   **Index pattern:** `brands`
    *   **Timestamp field:** Select *I don't want to use the time filter*.
3. Click **Save data view to Kibana**.

---

## 3. Exploring Mapped Fields (Discover)

Once data views are created, you can use the **Discover** tab to run queries and view indexed product documents:

1. Open the main menu on the left and navigate to **Analytics** ➔ **Discover**.
2. From the dropdown menu on the left side of the screen, select the `products` data view.
3. You can see your seeded test data here. You can add specific columns to the table (e.g., `title`, `price`, `brand_name`, `popularity_score`) by hovering over the field list on the left side and clicking the `+` sign.
4. Try typing a query in the search bar:
   *   `hp` (to find HP products)
   *   `price > 500` (to filter products by price range)

---

## 4. Setting up a Monitoring Dashboard

To create a visual dashboard of the product catalog:

1. Open the left menu and navigate to **Analytics** ➔ **Dashboard**.
2. Click **Create dashboard** (or **New dashboard**).
3. Click **Create visualization** (or drag-and-drop fields from the left panel).
4. Recommended Visualizations:
    *   **Product Price Distribution**: Select the `price` field and choose **Histogram** to see pricing brackets.
    *   **Categories Breakdown**: Drag `category_name.raw` to the workspace and select **Donut** or **Pie** chart.
    *   **Top Brands**: Drag `brand_name.raw` and set the visualization to **Bar chart** (ordered by document count).
    *   **Popularity Metric**: Add a **Metric** visualization showing the average of the `popularity_score` field.
5. Click **Save** in the top right corner and name your dashboard `SafeTrade Product Search Overview`.
