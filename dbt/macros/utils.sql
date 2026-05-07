{% macro safe_pct(numerator, denominator, scale=1) -%}
    round({{ numerator }} / nullif({{ denominator }}, 0)::float * 100, {{ scale }})
{%- endmacro %}
