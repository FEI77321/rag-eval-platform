-- RAG Lab schema; generated from SQLAlchemy models; MySQL 8 / utf8mb4.


CREATE TABLE api_calls (
	id VARCHAR(64) NOT NULL, 
	run_id VARCHAR(64), 
	item_id VARCHAR(64), 
	`role` VARCHAR(20) NOT NULL, 
	model VARCHAR(255) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	payload JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_api_calls_run_id ON api_calls (run_id);

CREATE INDEX ix_api_calls_item_id ON api_calls (item_id);


CREATE TABLE configs (
	id VARCHAR(64) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	parameters JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE datasets (
	id VARCHAR(64) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE documents (
	id VARCHAR(64) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	source_url VARCHAR(2048) NOT NULL, 
	content LONGTEXT NOT NULL, 
	content_hash VARCHAR(64) NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE index_cache (
	id VARCHAR(64) NOT NULL, 
	payload JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE runs (
	id VARCHAR(64) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	dataset_id VARCHAR(64) NOT NULL, 
	state VARCHAR(20) NOT NULL, 
	mode VARCHAR(12) NOT NULL, 
	concurrency INTEGER NOT NULL, 
	snapshot JSON NOT NULL, 
	owner VARCHAR(64), 
	heartbeat DATETIME, 
	error TEXT, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_runs_state ON runs (state);


CREATE TABLE questions (
	id VARCHAR(64) NOT NULL, 
	dataset_id VARCHAR(64) NOT NULL, 
	case_id VARCHAR(80) NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (dataset_id, case_id), 
	FOREIGN KEY(dataset_id) REFERENCES datasets (id)
)

;


CREATE TABLE run_items (
	id VARCHAR(64) NOT NULL, 
	run_id VARCHAR(64) NOT NULL, 
	config_id VARCHAR(64) NOT NULL, 
	case_id VARCHAR(80) NOT NULL, 
	state VARCHAR(20) NOT NULL, 
	attempts INTEGER NOT NULL, 
	generation JSON, 
	judgement JSON, 
	metrics JSON, 
	error TEXT, 
	tags JSON NOT NULL, 
	note TEXT NOT NULL, 
	human_review JSON, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (run_id, config_id, case_id), 
	FOREIGN KEY(run_id) REFERENCES runs (id)
)

;

CREATE INDEX ix_run_items_config_id ON run_items (config_id);

CREATE INDEX ix_run_items_run_id ON run_items (run_id);

CREATE INDEX ix_run_items_state ON run_items (state);