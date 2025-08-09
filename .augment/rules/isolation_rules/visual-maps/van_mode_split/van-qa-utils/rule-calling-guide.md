---
description: Comprehensive guide for calling VAN QA rules
globs: van_mode_split\van-qa-utils\rule-calling-guide.mdc
alwaysApply: false
---
# VAN QA: COMPREHENSIVE RULE CALLING GUIDE

> **TL;DR:** This reference guide shows how to properly call all VAN QA rules at the right time during the validation process.

## 🔍 RULE CALLING BASICS

Remember these key principles:
1. Always use the `fetch_rules` tool to load rules
2. Use exact rule paths
3. Load components only when needed

## 📋 MAIN QA ENTRY POINT

When user types "VAN QA", load the main entry point:

```
fetch_rules with "isolation_rules/visual-maps/van-qa-main"
```

## 📋 VALIDATION CHECKS

Load these components sequentially during validation:

```
1. fetch_rules with "isolation_rules/visual-maps/van-qa-checks/dependency-check"
2. fetch_rules with "isolation_rules/visual-maps/van-qa-checks/config-check"
3. fetch_rules with "isolation_rules/visual-maps/van-qa-checks/environment-check"
4. fetch_rules with "isolation_rules/visual-maps/van-qa-checks/build-test"
```

## 📋 UTILITY COMPONENTS

Load these when needed based on validation results:

```
- For reports: fetch_rules with "isolation_rules/visual-maps/van-qa-utils/reports"
- For fixes: fetch_rules with "isolation_rules/visual-maps/van-qa-utils/common-fixes"
- For transitions: fetch_rules with "isolation_rules/visual-maps/van-qa-utils/mode-transitions"
```

## ⚠️ CRITICAL REMINDERS

Remember to call these rules at these specific points:
- ALWAYS load the main QA entry point when "VAN QA" is typed
- ALWAYS load dependency-check before starting validation
- ALWAYS load reports after completing validation
- ALWAYS load mode-transitions after successful validation
- ALWAYS load common-fixes after failed validation

## 🔄 FULL VALIDATION SEQUENCE

Complete sequence for a QA validation process:

1. Load main entry: `isolation_rules/visual-maps/van-qa-main`
2. Load first check: `isolation_rules/visual-maps/van-qa-checks/dependency-check`
3. Load second check: `isolation_rules/visual-maps/van-qa-checks/config-check`
4. Load third check: `isolation_rules/visual-maps/van-qa-checks/environment-check`
5. Load fourth check: `isolation_rules/visual-maps/van-qa-checks/build-test`
6. If pass, load: `isolation_rules/visual-maps/van-qa-utils/reports`
7. If pass, load: `isolation_rules/visual-maps/van-qa-utils/mode-transitions` 
8. If fail, load: `isolation_rules/visual-maps/van-qa-utils/common-fixes` 