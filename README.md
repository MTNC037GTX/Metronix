# Metronix

**Web-Based Personal Financial Management System**

## Overview

Metronix is a web-based personal financial management system built using Flask. It is designed to provide clear, structured visibility into personal finances by tracking income, expenses, budgets, account balances, and monthly financial performance through a dashboard-driven interface.

This project prioritizes correctness, maintainability, and real-world financial workflows over visual gimmicks.

## Objectives

- Centralize personal financial data
- Track income and expenses accurately
- Maintain consistent and reconcilable account balances
- Provide executive-style financial summaries
- Use a scalable and modular system architecture

## Key Features

- User authentication with session management
- Account management
- Income, expense, and transfer transaction tracking
- Automatic balance updates per account
- Budget creation and tracking
- Monthly balance snapshot generation
- Financial overview dashboard including:
  - Total Income
  - Total Expense
  - Net Cash Flow (Income - Expense)
  - Savings Rate = (Income - Expense) / Income
- Consistent UI patterns across all pages
- PostgreSQL-backed persistent storage

## Tech Stack

### Backend
- Python
- Flask
- Flask Blueprints

### Frontend
- HTML
- Tailwind CSS
- JavaScript
- Jinja2 Templates

### Database
- PostgreSQL

## System Architecture

Metronix follows a modular Flask architecture built around Blueprints.

- Each feature is isolated into its own route module
- Business logic is handled in service layers
- Templates remain lightweight and presentation-focused
- Reusable UI components ensure consistency

This structure is designed for maintainability and controlled expansion.

## Design Philosophy

- Consistency over creativity
- Clarity over cleverness
- Business logic must not live in templates
- Financial data must always reconcile
- UI patterns are reused, not reinvented

## Current Development Status

- The project is **still under development**
- Finished pages: Landing, Dashboard, Account, Balance, Budget, Goals, Transactions
- Core backend structure and services are in place
- Remaining modules and features will be added iteratively

## Potential Future Improvements

- API-first architecture
- Role-based access control
- Advanced analytics and forecasting
- Export and reporting tools
- Mobile-first or cross-platform frontend

## License

**All Rights Reserved**

Copyright (c) 2026  
All rights reserved.

This source code is provided for viewing and evaluation purposes only.  
No permission is granted to copy, modify, distribute, or use this software, in whole or in part, without explicit written permission from the author.

## Final Note

Metronix represents a structured and pragmatic approach to personal finance software development. It emphasizes architectural discipline, data correctness, and long-term maintainability, making it suitable for academic evaluation and controlled sharing.
