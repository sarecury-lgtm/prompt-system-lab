# Shipping-Included Unit Price

## What To Check

- Item price
- Required delivery fee
- Total grams
- Bundle count and option-specific weight
- Free-shipping threshold only if the user intends to meet it

## Common Traps

- Cheap item price with high shipping
- Price shown for a smaller option than the target product
- Bundle count hidden in option text
- Free shipping that requires unrelated extra purchases

## Strong Evidence

- Product page shows exact item price, delivery fee, and total grams for the selected option.
- The 100g calculation can be reproduced.

## Mark Unknown

- Weight, option, shipping fee, or required bundle count is unclear.
- Price depends on coupons, app-only discounts, or subscriptions that are not guaranteed.

## Output Implications

- Required formula: `(item price + required delivery fee) / total grams * 100`.
- Exclude listings when delivery-included 100g price cannot be calculated.
