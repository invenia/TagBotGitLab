## {{ package }} {{ version }}

{% if previous_release %}
[Diff since {{ previous_release }}]({{ compare_url }})
{% endif %}

{% if issues %}
**Closed issues:**
{% for issue in issues %}
- {{ issue.title }} (#{{ issue.number }})
{% endfor %}
{% endif %}

{% if merge_requests %}
**Merged pull requests:**
{% for merge_request in merge_requests %}
- {{ merge_request.title }} (!{{ merge_request.number }}) (@{{ merge_request.author.username }})
{% endfor %}
{% endif %}
