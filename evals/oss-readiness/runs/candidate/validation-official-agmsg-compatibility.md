A fresh official agmsg 1.1.7 installation is supported. The wrapper uses
whoami.sh for identity, send.sh to submit the envelope, and official api.sh as
the local read-only JSONL reader. It correlates the returned request and reply by
the unique job_id. api.sh reads the local agmsg store with no network and is not an Anthropic API, so that read does not invoke a model or create model billing.
The installation dry-run validates this transport without sending a job or
running Fable or Sonnet.
