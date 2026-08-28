# Plain English Explainer

## Problem

Clinical review teams receive trial data from different sources such as labs, EDC systems, and adverse event reports. The work is often manual, repetitive, and hard to prioritize. Reviewers need to quickly answer questions like:

- Which records are missing critical values?
- Which results are outside expected ranges?
- Which records are stale or duplicated?
- Which issues are urgent enough to send back to sites?

## Solution

This project creates a lightweight clinical review command center that reads trial-like data, detects data quality issues, ranks the seriousness, and generates reviewer-ready follow-up queries. It packages this in a polished dashboard so the review process can be explained clearly to both technical and business stakeholders.

## What the system does

1. Loads a clinical dataset from CSV.
2. Validates the required schema.
3. Runs quality checks using PySpark DataFrame logic.
4. Runs the same checks in Spark SQL.
5. Confirms both sides agree on the flagged records.
6. Assigns severity such as high or medium.
7. Drafts a short message for each flagged item.
8. Produces a summary and dashboard for operational review.

## Why this matters

This is not a replacement for an enterprise clinical platform. It is a realistic demonstration of the core work a clinical review process must do: detect issues, focus attention, and reduce manual review effort.

## What is included

- a review dashboard
- a working local Spark pipeline
- dataset upload support
- CSV and PDF exports
- auditability via DataFrame and SQL validation
- demo data plus a reusable structure for uploaded datasets

## What it is not

- not a medical decision engine
- not connected to a real clinical database
- not a fully validated production system
- not an LLM-based reviewer assistant

## One-line summary

This project automates the first pass of clinical data review by detecting quality issues early, prioritizing them, and presenting them in a professional dashboard for review teams.
