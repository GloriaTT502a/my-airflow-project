-- update the existing rows 
UPDATE public.stock_prices p
SET 
    open_price = s.open_price,
    high_price = s.high_price,
    low_price = s.low_price,
    close_price = s.close_price,
    updated_at = now()
FROM public.stock_prices_stage s
WHERE p.ticker = s.ticker
AND p.as_of_date = s.as_of_date;

-- inserting new rows 
INSERT INTO stock_prices 
(ticker, as_of_date, open_price, high_price, low_price, close_price)
SELECT 
    s.ticker, 
    s.as_of_date, 
    s.open_price, 
    s.high_price, 
    s.low_price, 
    s.close_price
FROM stock_prices_stage s
WHERE NOT EXISTS (
    SELECT 1 
    FROM stock_prices p 
    WHERE p.ticker = s.ticker 
    AND p.as_of_date = s.as_of_date
);

-- truncate the stage table; 
truncate table stock_prices_stage; 

