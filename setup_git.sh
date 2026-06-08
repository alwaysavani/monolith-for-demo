#!/bin/bash
git init

git config user.name "Alice Platform"
git config user.email "alice@example.com"
git add core_infra/feature_flags.py
git commit -m "[PLAT-909] Init feature flags"

git config user.name "Bob Billing"
git config user.email "bob@example.com"
git add billing_module/payment_gateway.py
git commit -m "[PAY-555] Create payment gateway"

git config user.name "Charlie Logistics"
git config user.email "charlie@example.com"
git add fulfillment_module/shipping_calculator.py
git commit -m "[LOG-402] Setup shipping calc"

git config user.name "Dave Frontend"
git config user.email "dave@example.com"
git add frontend_api/graphql_resolvers.py
git commit -m "[WEB-101] Add GraphQL checkout resolver"

git config user.name "Avani DevOps"
git config user.email "avani@example.com"
git add .
git commit -m "Add CI/CD scripts and issues data"

git branch -M main
git remote add origin https://github.com/alwaysavani/monolith-for-demo.git
git push -u origin main
