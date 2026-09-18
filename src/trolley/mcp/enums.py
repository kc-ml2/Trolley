from enum import StrEnum


class SystemToolName(StrEnum):
    GET_EXECUTION = "get_execution"
    GET_MY_CAPABILITIES = "get_my_capabilities"
    QUERY_TARGET = "query_target"
    LIST_TARGETS = "list_targets"
    GET_TARGET_SCHEMA = "get_target_schema"
    GET_TARGET_NOTES = "get_target_notes"
    UPDATE_TARGET_NOTES = "update_target_notes"
    LIST_OPERATIONS = "list_operations"
    CREATE_OPERATION = "create_operation"
    UPDATE_OPERATION = "update_operation"
    DISABLE_OPERATION = "disable_operation"
    EXECUTE = "execute"
