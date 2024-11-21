# SQL

## Debug Events that are not supposed to be there (e.g. connect without a disconnect, or two disconnects)

```sql
SELECT id, display_name, ubisoft_username_max, ubisoft_username_active, time_zone FROM user_info WHERE display_name LIKE 'seklaw%';
select timestamp, event, id from user_activity where user_id = 648700275191709735 order by timestamp asc;
delete from user_activity where id = 1262;
delete from user_activity where id = 754;
delete from user_activity where id = 1269;
delete from user_activity where id = 1270;
```
