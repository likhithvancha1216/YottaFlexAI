# Supplier Acknowledgement Generator

## 1. Project Overview

The Supplier Acknowledgement Generator is a Python-based data generation and validation project that simulates a procurement lifecycle.

It models interactions between suppliers and purchasing organizations, including purchase orders, supplier acknowledgements, delivery promises, change requests, approval decisions, inventory planning, production requirements, and downstream notifications.

The system generates interconnected datasets with realistic relationships and business rules. It also injects four deliberately designed data anomalies for validation and analysis.

The project demonstrates:

* Structured and deterministic synthetic data generation.
* Procurement business-rule implementation.
* Change approval and decision workflows.
* Historical inventory-plan versioning.
* Production material allocation.
* Downstream supply-impact notifications.
* Data integrity validation.
* Automated testing.

## 2. Technology Stack

| Technology                | Purpose                                                               |
| ------------------------- | --------------------------------------------------------------------- |
| Python 3.12               | Main programming language                                             |
| Standard Python libraries | Random generation, date handling, CSV processing, and data structures |
| pytest                    | Automated testing                                                     |
| CSV                       | Dataset storage and exchange                                          |
| PowerShell                | Running commands in the Windows environment                           |

No external database is required for the current implementation.

## 3. Project Structure

```text
supplier-ack-generator/
|
|-- generate.py
|-- README.md
|-- requirements.txt
|
|-- src/
|   |-- __init__.py
|   |-- config.py
|   |-- ids.py
|   |-- rules.py
|   |-- validate.py
|   |-- export.py
|   |
|   |-- generators/
|       |-- __init__.py
|       |-- suppliers.py
|       |-- purchase_orders.py
|       |-- acknowledgements.py
|       |-- changes.py
|       |-- downstream.py
|       |-- anomalies.py
|
|-- tests/
|   |-- tests_generators.py
|   |-- test_ids.py
|   |-- test_rules.py
|   |-- test_changes.py
|   |-- test_downstream.py
|   |-- test_anomalies.py
|
|-- docs/
|   |-- data_dictionary.md
|
|-- output/
    |-- Generated CSV files
```

## 4. System Workflow

The system follows a sequence of dependent data-generation stages:

1. Generate supplier master records.
2. Generate purchase orders and their individual lines.
3. Generate supplier acknowledgement revisions.
4. Generate supplier delivery promises.
5. Compare acknowledgement values with the original purchase-order terms.
6. Create change requests when supplier terms differ.
7. Evaluate approval requirements using business rules.
8. Generate approval decisions and records.
9. Generate versioned inventory plans using applied changes.
10. Generate production orders and their PO-line allocations.
11. Identify downstream supply impacts and generate notifications.
12. Inject four labelled anomalies into the output datasets.
13. Export datasets as CSV files.
14. Validate generated records and relationships.

## 5. Business Rules

### 5.1 Change Detection

A change request is generated when the supplier's acknowledgement differs from the original purchase-order terms.

The system evaluates:

**Price change percentage**

`(Proposed Price - Requested Price) / Requested Price * 100`

**Quantity shortfall percentage**

`(Ordered Quantity - Accepted Quantity) / Ordered Quantity * 100`

**Delivery date slip**

`Promised Date - Requested Date`

When all three differences are zero, no change request is created.

### 5.2 Approval Rules

The system uses configurable thresholds to determine whether a change can be automatically approved or requires a human decision.

| Condition                                              | Outcome          | Responsible role         |
| ------------------------------------------------------ | ---------------- | ------------------------ |
| All changes are within thresholds                      | AUTO_APPROVED    | SYSTEM                   |
| Supplier declines the entire line                      | APPROVED         | OPS_MANAGER              |
| Any change exceeds a hard limit                        | REJECTED         | OPS_MANAGER              |
| One threshold is breached within hard limits           | APPROVED         | PLANNER                  |
| Two or more thresholds are breached within hard limits | APPROVED         | OPS_MANAGER              |
| Human decision is still pending                        | PENDING_APPROVAL | No decision recorded yet |

A pending change does not have an approval record until a decision is made.

Automatically approved changes also receive approval records for traceability.

### 5.3 Inventory Plan Rules

The inventory plan maintains historical versions of expected supply for each purchase-order line.

* Version 1 represents the original ordered quantity and requested date.
* Approved changes create subsequent plan versions.
* Rejected changes do not update the plan.
* Pending changes do not update the plan.
* Previous versions are retained rather than overwritten.
* Effective dates establish when each version applies.

Applied change statuses:

* AUTO_APPROVED
* APPROVED

### 5.4 Production Order Rules

Production orders represent manufacturing requirements that consume purchased materials.

A many-to-many relationship connects production orders and purchase-order lines through `production_order_po_line.csv`.

The allocation logic ensures that the total allocated quantity of a PO line does not exceed its original ordered quantity.

### 5.5 Notification Rules

Notifications are generated when an applied supply change affects a production order.

The system identifies:

* Delivery delays.
* Quantity shortfalls.
* Combined delivery delays and quantity shortfalls.

Notifications are sent to the planner responsible for the affected production order.

## 6. Generated Datasets

The project produces 12 CSV datasets.

| Dataset                      | Description                                    |
| ---------------------------- | ---------------------------------------------- |
| suppliers.csv                | Supplier master records                        |
| purchase_orders.csv          | Purchase-order records                         |
| po_lines.csv                 | Individual purchase-order lines                |
| acknowledgements.csv         | Supplier acknowledgement records               |
| promises.csv                 | Supplier delivery promises                     |
| changes.csv                  | Supplier-requested changes                     |
| approvals.csv                | Approval decisions                             |
| inventory_plan.csv           | Versioned expected supply records              |
| production_orders.csv        | Manufacturing requirements                     |
| production_order_po_line.csv | Production-to-purchase-order allocation bridge |
| notifications.csv            | Downstream impact notifications                |
| ground_truth.csv             | Labels for injected anomalies                  |

Detailed column descriptions and relationships are available in `docs/data_dictionary.md`.

## 7. Current Generated Dataset Statistics

The following counts are from the successful run using:

`python generate.py --n-pos 10000`

| Dataset                        | Generated records |
| ------------------------------ | ----------------: |
| Suppliers                      |               200 |
| Purchase orders                |            10,000 |
| PO lines                       |            14,981 |
| Acknowledgements               |            15,705 |
| Promises                       |            15,155 |
| Changes                        |             8,780 |
| Approvals                      |             8,706 |
| Inventory plans                |            22,087 |
| Production orders              |             2,975 |
| Production-order/PO-line links |             5,557 |
| Notifications                  |               810 |
| Ground-truth anomalies         |                 4 |

**Event-count interpretation:** The current implementation generates 15,705 acknowledgement records and 8,780 change records, or 24,485 records combined. This implementation treats the acknowledgement target and the derived change records as separate dataset counts. If the original requirement intends 15,000 as a combined total, the generator's configuration must be adjusted accordingly.

## 8. Anomaly Injection

Four deliberate anomalies are introduced for testing and analysis.

| Anomaly                             | Description                                                               |
| ----------------------------------- | ------------------------------------------------------------------------- |
| UNAPPROVED_CHANGE_UPDATES_INVENTORY | An unapproved change incorrectly updates an inventory plan                |
| ACK_POINTS_TO_WRONG_PO_LINE         | An acknowledgement references an incorrect PO line                        |
| PROMISED_DATE_BEFORE_ORDER_DATE     | A promised delivery date occurs before the purchase-order date            |
| OLDER_REVISION_OVERWRITES_NEWER     | An older acknowledgement revision incorrectly overwrites a newer revision |

Each anomaly is labelled in `ground_truth.csv`, allowing the affected records to be identified.

These anomalies are intentional test scenarios and should not be confused with ordinary generated records.

## 9. Deterministic Data Generation

The project uses a configured random seed to make generated data reproducible.

The default seed is:

`20261022`

Using the same seed and configuration produces repeatable output.

This makes it easier to test business rules, investigate data issues, and compare results across runs.

## 10. Installation and Execution

### Prerequisites

* Python 3.12 or a compatible Python version.
* Windows PowerShell or another terminal.
* pytest for running automated tests.

### Step 1: Open the project directory

```powershell
cd C:\Users\Dell\Desktop\supplier-ack-generator
```

### Step 2: Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### Step 3: Generate datasets

```powershell
python generate.py --n-pos 10000
```

### Step 4: Validate datasets

```powershell
python -m src.validate
```

### Step 5: Run automated tests

```powershell
python -m pytest -v
```

## 11. Validation

The validation module checks generated CSV files for data integrity and business consistency.

Validation includes:

* Expected dataset files.
* Expected column structures.
* Primary-key uniqueness.
* Foreign-key relationships.
* Acknowledgement and PO-line consistency.
* Approval and change-status consistency.
* Change supersede-chain relationships.
* Inventory-plan version consistency.
* Approved-only inventory updates.
* Production allocation limits.
* Notification relationships and recipients.
* Numeric and date validity.
* Presence of all four required anomaly labels.

### Current Validation Result

The latest execution reported:

* Errors: 0
* Warnings: 0
* Result: VALIDATION PASSED

### Current Automated Test Result

The latest pytest execution reported:

* Tests collected: 19
* Tests passed: 19
* Tests failed: 0

These are the results from the current tested configuration.

## 12. Design Considerations

### Separation of Responsibilities

The project separates configuration, identifiers, business rules, data generation, validation, and export operations into different modules.

This makes the code easier to understand, test, and maintain.

### Data Relationships

Related datasets use identifiers to maintain referential integrity.

### Historical Traceability

Inventory-plan versions preserve historical supply expectations rather than replacing previous records.

### Reproducibility

A fixed random seed makes the generation process repeatable.

### Testability

Business rules and generator functions are tested independently using pytest.

## 13. Assumptions and Limitations

* The generated records are synthetic and do not represent real suppliers or purchase orders.
* Approval thresholds are configurable project assumptions.
* The simulated environment uses a fixed `as_of_date` rather than the actual current date.
* CSV files are used for data storage and exchange.
* The current approval model records the decision associated with each change request.
* The project models a simplified procurement and downstream planning workflow.
* Notifications represent simulated notification records rather than actual external messages.
* The current event counts are documented separately; the combined event total is 24,485.
* Identifier formats are implementation conventions used to maintain consistent references across datasets.
* The current notification model can create separate notifications for separate applied changes affecting the same production order.

## 14. Future Enhancements

Potential future improvements include:

* Database integration.
* Interactive analytics dashboard.
* REST API integration.
* More advanced anomaly detection.
* Configurable approval policies.
* Additional notification channels.
* Larger-scale performance testing.
* Historical reporting and analysis.

## 15. AI Assistance and Code Ownership

AI assistance was used during parts of the development process for explanations, implementation guidance, debugging support, and documentation preparation.

The developer is responsible for reviewing, understanding, testing, and explaining the final implementation.

All implementation decisions and generated results should be verified against the project requirements before submission.

---

**Project:** Supplier Acknowledgement Generator
**Language:** Python
**Output Format:** CSV
**Testing Framework:** pytest
**Current Test Result:** 19 passed
**Current Validation Result:** Passed
