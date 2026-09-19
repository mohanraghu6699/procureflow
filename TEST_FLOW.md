# ProcureFlow — Manual test flow

Purchase Request → Approval → Purchase Order → Delivery → Completion.
Use two browser profiles (or a normal + an incognito window) so you can stay logged in as two roles at once.

## Accounts (seeded)

| Role | Login | Password |
|---|---|---|
| Requester | rohan.sharma@procureflow.com | Requester@123 |
| Requester | priya.nair@procureflow.com | Requester@123 |
| Approver | sameer.khan@procureflow.com | Approver@123 |
| Approver | amit.patel@procureflow.com | Approver@123 |
| Admin | admin@procureflow.com | Admin@123 |

## Vendors per category (seeded)

| Category | Vendors |
|---|---|
| Spare Parts | Gulf Marine Supplies LLC |
| Safety Equipment | Gulf Marine Supplies LLC, SafetyFirst Equipment Trading |
| IT Hardware | TechZone Computers, Al Futtaim Office Solutions |
| Office Furniture | Al Futtaim Office Solutions |
| Catering Services | Prime Catering Co. |
| Professional Services | Gulf Advisory Partners |

## Happy path

- [ ] **0. (Optional) Master data — Admin.** Master Data: add a department / category / vendor and tick the categories the vendor supplies (the **Categories** button on a vendor edits them later). Users: create a login with the **Generate** password button.
- [ ] **1. Create the PR — Rohan.** Purchase Requests → **+ New Purchase Request**.
  - Vendor is disabled until a category is picked, then lists only vendors supplying it; changing the category clears the vendor.
  - Fill description, department, amount, required date (today or later) → **Create Draft**. Status `DRAFT`, first history entry.
  - Try **Edit**, then **Submit for Approval** → `SUBMITTED`, Edit disappears.
- [ ] **2. Approve — Sameer.** Approvals → open the PR → optional comment → **Approve** → `APPROVED`; history shows who/when.
- [ ] **3. Create the PO — Sameer.** On the approved PR's detail page → **Create Purchase Order**.
  - Vendor list limited to vendors supplying the PR's category (hint shown under it).
  - PO opens as `OPEN`; the PR page links to it.
- [ ] **4. Deliver — Sameer.** On the PO page:
  - Updates can repeat in any order: **In transit** → **Partial** → **In transit** → **Partial** → …. Each one is stamped with time and user; none needs a date.
  - **In transit** → PO `IN_TRANSIT`; **Partial** → PO `PARTIALLY_DELIVERED`.
  - Finish with **Delivered** (date picker appears, from the PO's creation date up to today) → PO and PR both `COMPLETED`, delivery form disappears. Delivered is the only final status.
  - Deliveries page lists both records.
  - **Required By** (from the PR) shows on the PO with a badge: `Due in N days` / `Due today` / `Overdue by N days` while open, then `On time` / `N days late` once delivered. Each delivery entry is badged the same way, and the PO list has a **Required By** column with a red "Overdue" marker.
  - Delivery date can't be in the future or before the PO was created.
- [ ] **5. Verify.** Rohan sees his PR `COMPLETED` and the PO read-only. Dashboard totals, status donut, monthly chart and Recent Activity all match.

## Edge cases

- [ ] **Reject & resubmit:** Sameer rejects → Rohan sees `REJECTED`, edits, resubmits; history shows the full trail.
- [ ] **Vendor rules:**
  - [ ] Change category after picking a vendor → vendor clears.
  - [ ] Master Data: remove a category from a vendor → vendor disappears from that category's list.
  - [ ] Vendor with no categories → shows a warning and appears in no list.
- [ ] **Validation:** past required date; amount 0 / negative.
- [ ] **Self-approval:** Admin creates + submits a PR, then tries to approve it → blocked.
- [ ] **Role separation:**
  - [ ] Rohan opens `/approvals` by URL → redirected to dashboard.
  - [ ] Rohan opens Priya's PR by URL → denied.
  - [ ] Sameer sees no "New Purchase Request" button.
- [ ] **One PO per PR:** once a PO exists, the Create PO button is gone.
- [ ] **Delivered without a date** → blocked.
- [ ] **Deleting drafts:** create 3 PRs, delete the first draft, create another → numbers don't collide.
- [ ] **Search / filter / sort / pagination:** need 11+ PRs to see page 2.
- [ ] **Mobile / narrow window (~400 px, or browser device mode):** sidebar hides behind the ☰ menu button and closes after you pick a page; tables scroll sideways; forms stack to one column; detail-page buttons wrap; nothing forces the whole page to scroll sideways.
- [ ] **Change password:** avatar (top right) → Change Password; cancel clears the fields.
- [ ] **Session:** refresh keeps you logged in; token lasts 8 hours from login.
