# Dispatch / who can go onsite

This is Operator. Trends only wrote the stamp.

They named a site or group (or “who can go onsite”). That is
a read. Do not require a lab marker for this ask.

## Order

1. `read_file` `servicenow/metadata-trends.json`. If
   `last_visit_id` is set, that stamp. Do not invent trends.
   No stamp: say trends are not on disk yet; still answer from
   live groups.
2. Resolve the pool: metadata `assignment_groups[]`, or
   `snow_find_assignment_groups` for the site/group they
   named. Then `snow_list_group_members` (and
   `snow_find_users` if needed). Do not invent names.
3. For members on an **open** INC: `snow_get_incident` (or
   the stamp `open_consuming[]`). Busy = assigned to an open
   ticket.
4. If that open ticket’s number or theme is on a stamp
   cluster with `recommend` `kb`: they are local but tied up
   on a repeating ticket. Say a KB (or the existing
   `kb_number`) would free them for onsite. Offer a member
   who is **not** on an open ticket for true onsite work.
5. Do not draft the KB until they ask this turn
   (`references/knowledge.md`). Do not assign until they
   name the person this turn.

Never dump the instance. Never write `servicenow/trends/`.
