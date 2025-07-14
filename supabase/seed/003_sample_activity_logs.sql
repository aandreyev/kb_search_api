-- Sample activity logs for testing user activity tracking
-- These represent typical user interactions with the knowledge base search application

INSERT INTO activity_logs (
    user_id,
    username,
    event_type,
    search_term,
    document_id,
    document_filename,
    preview_type,
    details,
    created_at
) VALUES 
-- User login activities
(
    'd04b9ecd-da2e-466f-8a46-22bdde03f362',
    'andrew@adlvlaw.com.au',
    'USER_LOGIN_SUCCESS',
    NULL,
    NULL,
    NULL,
    NULL,
    '{"login_method": "azure_ad", "session_duration_estimate": "2_hours"}',
    '2024-07-14 09:15:22'::timestamp
),
(
    'e15c0fde-eb3f-577g-9b57-33cee04g463',
    'sarah.mitchell@commerciallaw.com.au',
    'USER_LOGIN_SUCCESS',
    NULL,
    NULL,
    NULL,
    NULL,
    '{"login_method": "azure_ad", "session_duration_estimate": "1_hour"}',
    '2024-07-14 09:45:18'::timestamp
),

-- Search activities
(
    'd04b9ecd-da2e-466f-8a46-22bdde03f362',
    'andrew@adlvlaw.com.au',
    'SEARCH_SUBMITTED',
    'small business CGT concessions',
    NULL,
    NULL,
    NULL,
    '{"search_type": "semantic", "results_count": 5, "response_time_ms": 1250}',
    '2024-07-14 09:18:45'::timestamp
),
(
    'd04b9ecd-da2e-466f-8a46-22bdde03f362',
    'andrew@adlvlaw.com.au',
    'SEARCH_SUBMITTED',
    'restraint of trade executives',
    NULL,
    NULL,
    NULL,
    '{"search_type": "semantic", "results_count": 3, "response_time_ms": 980}',
    '2024-07-14 09:22:15'::timestamp
),
(
    'e15c0fde-eb3f-577g-9b57-33cee04g463',
    'sarah.mitchell@commerciallaw.com.au',
    'SEARCH_SUBMITTED',
    'directors duties corporations act',
    NULL,
    NULL,
    NULL,
    '{"search_type": "semantic", "results_count": 4, "response_time_ms": 1100}',
    '2024-07-14 09:48:33'::timestamp
),

-- Document preview activities
(
    'd04b9ecd-da2e-466f-8a46-22bdde03f362',
    'andrew@adlvlaw.com.au',
    'DOC_PREVIEW',
    NULL,
    '1',
    'ato_small_business_cgt_2023.pdf',
    'pdf_inline',
    '{"preview_duration_estimate": "5_minutes", "search_term_origin": "small business CGT concessions"}',
    '2024-07-14 09:19:12'::timestamp
),
(
    'd04b9ecd-da2e-466f-8a46-22bdde03f362',
    'andrew@adlvlaw.com.au',
    'DOC_PREVIEW',
    NULL,
    '2',
    'restraint_trade_executives_2024.docx',
    'pdf_inline',
    '{"preview_duration_estimate": "3_minutes", "search_term_origin": "restraint of trade executives"}',
    '2024-07-14 09:23:05'::timestamp
),
(
    'e15c0fde-eb3f-577g-9b57-33cee04g463',
    'sarah.mitchell@commerciallaw.com.au',
    'DOC_PREVIEW',
    NULL,
    '3',
    'directors_duties_commentary.pdf',
    'pdf_inline',
    '{"preview_duration_estimate": "8_minutes", "search_term_origin": "directors duties corporations act"}',
    '2024-07-14 09:49:15'::timestamp
),

-- Document download activities
(
    'd04b9ecd-da2e-466f-8a46-22bdde03f362',
    'andrew@adlvlaw.com.au',
    'DOC_DOWNLOAD_ATTEMPT',
    NULL,
    '1',
    'ato_small_business_cgt_2023.pdf',
    NULL,
    '{"download_reason": "client_consultation", "file_size_mb": 2.3}',
    '2024-07-14 09:24:30'::timestamp
),
(
    'e15c0fde-eb3f-577g-9b57-33cee04g463',
    'sarah.mitchell@commerciallaw.com.au',
    'DOC_DOWNLOAD_ATTEMPT',
    NULL,
    '3',
    'directors_duties_commentary.pdf',
    NULL,
    '{"download_reason": "research", "file_size_mb": 1.8}',
    '2024-07-14 09:57:22'::timestamp
),

-- Additional search activities for testing hybrid search
(
    'd04b9ecd-da2e-466f-8a46-22bdde03f362',
    'andrew@adlvlaw.com.au',
    'SEARCH_SUBMITTED',
    'ATO ruling GST professional services',
    NULL,
    NULL,
    NULL,
    '{"search_type": "semantic", "results_count": 2, "response_time_ms": 890}',
    '2024-07-14 10:15:45'::timestamp
),
(
    'e15c0fde-eb3f-577g-9b57-33cee04g463',
    'sarah.mitchell@commerciallaw.com.au',
    'SEARCH_SUBMITTED',
    'mining safety compliance WA',
    NULL,
    NULL,
    NULL,
    '{"search_type": "semantic", "results_count": 3, "response_time_ms": 1150}',
    '2024-07-14 10:05:18'::timestamp
),
(
    'd04b9ecd-da2e-466f-8a46-22bdde03f362',
    'andrew@adlvlaw.com.au',
    'SEARCH_SUBMITTED',
    'essential facilities doctrine ACCC',
    NULL,
    NULL,
    NULL,
    '{"search_type": "semantic", "results_count": 1, "response_time_ms": 750}',
    '2024-07-14 10:25:33'::timestamp
),

-- User logout activities
(
    'e15c0fde-eb3f-577g-9b57-33cee04g463',
    'sarah.mitchell@commerciallaw.com.au',
    'USER_LOGOUT_ATTEMPT',
    NULL,
    NULL,
    NULL,
    NULL,
    '{"session_duration_actual": "68_minutes", "searches_performed": 2, "documents_viewed": 1}',
    '2024-07-14 10:53:45'::timestamp
),
(
    'd04b9ecd-da2e-466f-8a46-22bdde03f362',
    'andrew@adlvlaw.com.au',
    'USER_LOGOUT_ATTEMPT',
    NULL,
    NULL,
    NULL,
    NULL,
    '{"session_duration_actual": "95_minutes", "searches_performed": 4, "documents_viewed": 2, "downloads_attempted": 1}',
    '2024-07-14 10:50:15'::timestamp
); 