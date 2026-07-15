The call should be reported as completed with actual_model, billing_mode=subscription,
subscription_type, and elapsed time. The local total_cost_usd value is only a
Claude CLI estimate and must not be presented as a subscriber invoice. If the
installed agmsg version is incompatible, add a narrow api.sh compatibility
fallback and retest the request and response correlation.
