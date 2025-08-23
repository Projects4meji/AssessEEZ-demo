<?php

use App\Http\Controllers\API\AuthController;
use App\Http\Controllers\API\InvoiceController;
use App\Http\Controllers\API\QualificationController;
use App\Http\Controllers\API\ResourceMaterialController;
use App\Http\Controllers\API\UserController;
use App\Http\Controllers\API\UserDeliveryAddressController;
use App\Http\Controllers\API\UserRolePermissionController;
use Illuminate\Support\Facades\Route;

// Route::get('/user', function (Request $request) {
//     return $request->user();
// })->middleware('auth:sanctum');


Route::prefix('v1')->middleware('api')->group(static function (): void {
    Route::post('get_places', [UserController::class, 'get_places']);
    Route::get('admin_dashboard', [UserController::class, 'admin_dashboard']);
    Route::get('get_types', [UserController::class, 'get_types']);

    Route::prefix('users')->group(static function (): void {
        Route::post('sign_up', [AuthController::class, 'sign_up']);
        Route::post('login', [AuthController::class, 'login']);
        Route::post('resend_otp', [AuthController::class, 'resend_otp']);
        Route::post('verify_otp', [AuthController::class, 'verify_otp']);
        Route::post('forgot_password', [AuthController::class, 'forgot_password']);
        Route::post('verify_forgot_password', [AuthController::class, 'verify_forgot_password']);
        // Route::post('resend_forgot_password_otp', [AuthController::class, 'resend_forgot_password_otp']);
        Route::post('change_forgot_password', [AuthController::class, 'change_forgot_password']);
        Route::get('get_user_statuses', [AuthController::class, 'get_user_statuses']);

        Route::get('get_assessors_list', [UserController::class, 'get_assessors_list']);
        Route::get('get_assessors', [UserController::class, 'get_assessors']);
        Route::get('get_assessorsV1', [UserController::class, 'get_assessorsV1']);
        Route::get('get_assessorsV2', [UserController::class, 'get_assessorsV2']);
        Route::get('get_iqas', [UserController::class, 'get_iqas']);
        Route::get('get_iqasV1', [UserController::class, 'get_iqasV1']);
        Route::get('get_iqasV2', [UserController::class, 'get_iqasV2']);
        Route::get('get_references', [UserController::class, 'get_references']);
        Route::get('get_learners', [UserController::class, 'get_learners']);
        Route::get('download_portfolio', [UserController::class, 'download_portfolio']);
        Route::get('send_reset_password_link', [AuthController::class, 'send_reset_password_link']);
    });

    Route::prefix('invoices')->group(static function (): void {
        Route::get('generate_invoice_job', [InvoiceController::class, 'generate_invoice_job']);
        Route::get('generate_invoice_pdf', [InvoiceController::class, 'generate_invoice_pdf']);
    });
    // Routes that require authentication
    Route::middleware('auth:sanctum')->group(static function (): void {
        Route::prefix('users')->group(static function (): void {
            Route::post('update_profile', [UserController::class, 'update_profile']);
            Route::post('update_profile_picture', [UserController::class, 'update_profile_picture']);
            Route::post('change_email_otp', [UserController::class, 'change_email_otp']);
            Route::post('change_email', [UserController::class, 'change_email']);
            Route::post('change_password', [UserController::class, 'change_password']);
            Route::post('change_password_by_admin', [UserController::class, 'change_password_by_admin']);
            Route::delete('delete_account', [UserController::class, 'delete_account']);
            Route::post('action_user_status', [UserController::class, 'action_user_status']);
            Route::post('update_user_address', [UserController::class, 'update_user_address']);
            Route::post('update_payment_method', [UserController::class, 'update_payment_method']);

            Route::post('create_user', [UserController::class, 'create_user']);
            Route::post('bulk_user_edit', [UserController::class, 'bulk_user_edit']);
            Route::get('get_users', [UserController::class, 'get_users']);
            Route::get('get_users_V1', [UserController::class, 'get_users_V1']);
            Route::get('get_users_name', [UserController::class, 'get_users_name']);
            Route::get('get_user_roles', [UserController::class, 'get_user_roles']);
            Route::get('get_batch_no', [UserController::class, 'get_batch_no']);


            Route::get('get_user_detail', [UserController::class, 'get_user_detail']);
            Route::get('get_user_detail_V1', [UserController::class, 'get_user_detail_V1']);
            Route::get('get_assigned_learners', [UserController::class, 'get_assigned_learners']);

            //Communications
            Route::post('send_message', [UserController::class, 'send_message']);
            Route::get('get_message', [UserController::class, 'get_message']);
            Route::post('mark_seen', [UserController::class, 'mark_seen']);

            // user import
            Route::post('user_import', [UserController::class, 'user_import']);

            Route::get('get_number_format', [UserController::class, 'get_number_format']);

            // summary
            Route::get('get_summary_user_qualification', [UserController::class, 'get_summary_user_qualification']);
            Route::get('get_qualification_bars', [UserController::class, 'get_qualification_bars']);


            // Route::get('get_learner_list', [UserController::class, 'get_learner_list']);
            Route::post('change_sampling_ratio', [UserController::class, 'change_sampling_ratio']);

            // customer
            Route::post('create_customer', [UserController::class, 'create_customer']);
            Route::get('get_customer', [UserController::class, 'get_customer']);
            Route::post('action_customer_status', [UserController::class, 'action_customer_status']);

            // assessor document
            Route::post('save_assessor_documents', [UserController::class, 'save_assessor_documents']);
            Route::get('get_assessor_documents', [UserController::class, 'get_assessor_documents']);

            // analyrics 
            Route::get('get_analytics', [UserController::class, 'get_analytics']);
        });

        Route::prefix('role_permission')->group(static function (): void {
            Route::post('roles', [UserRolePermissionController::class, 'roles']);
            Route::delete('delete_roles', [UserRolePermissionController::class, 'delete_roles']);
            Route::get('get_roles', [UserRolePermissionController::class, 'get_roles']);

            Route::post('permissions', [UserRolePermissionController::class, 'permissions']);
            Route::delete('delete_permissions', [UserRolePermissionController::class, 'delete_permissions']);
            Route::get('get_permissions', [UserRolePermissionController::class, 'get_permissions']);

            Route::post('user_roles', [UserRolePermissionController::class, 'user_roles']);
            Route::delete('delete_user_roles', [UserRolePermissionController::class, 'delete_user_roles']);
            Route::get('get_user_roles', [UserRolePermissionController::class, 'get_user_roles']);

            Route::post('role_permissions', [UserRolePermissionController::class, 'role_permissions']);
            Route::delete('delete_role_permissions', [UserRolePermissionController::class, 'delete_role_permissions']);
            Route::get('get_role_permissions', [UserRolePermissionController::class, 'get_role_permissions']);

            Route::post('permission_type', [UserRolePermissionController::class, 'permission_type']);
            Route::delete('delete_permission_type', [UserRolePermissionController::class, 'delete_permission_type']);
            Route::get('get_permission_type', [UserRolePermissionController::class, 'get_permission_type']);

            Route::post('permission_permission_type', [UserRolePermissionController::class, 'permission_permission_type']);
            Route::delete('delete_permission_permission_type', [UserRolePermissionController::class, 'delete_permission_permission_type']);
            Route::get('get_permission_permission_type', [UserRolePermissionController::class, 'get_permission_permission_type']);

            Route::get('get_role_permission_by_user', [UserRolePermissionController::class, 'get_role_permission_by_user']);
            Route::get('get_role_permission_and_types', [UserRolePermissionController::class, 'get_role_permission_and_types']);
            Route::post('add_role_with_per_and_type', [UserRolePermissionController::class, 'add_role_with_per_and_type']);
            Route::post('team_status_change', [UserRolePermissionController::class, 'team_status_change']);
        });

        Route::prefix('qualifications')->group(static function (): void {
            Route::get('get_qualifications', [QualificationController::class, 'get_qualifications']);
            Route::get('get_qualificationsV1', [QualificationController::class, 'get_qualificationsV1']);
            Route::get('get_qualificationsV2', [QualificationController::class, 'get_qualificationsV2']);

            Route::get('get_qualificationsV3', [QualificationController::class, 'get_qualificationsV3']);

            Route::get('get_qualification_by_id', [QualificationController::class, 'get_qualification_by_id']);
            Route::get('get_assigned_qualifications', [QualificationController::class, 'get_assigned_qualifications']);
            Route::get('get_parent_qualifications', [QualificationController::class, 'get_parent_qualifications']);
            Route::get('get_superadmin_qualifications', [QualificationController::class, 'get_superadmin_qualifications']);
            Route::delete('delete_qualification', [QualificationController::class, 'delete_qualification']);
            Route::post('save_qualification', [QualificationController::class, 'save_qualification']);
            Route::post('update_qualification', [QualificationController::class, 'update_qualification']);

            Route::get('get_documents', [QualificationController::class, 'get_documents']);
            Route::post('superadmin_qualification_transfer', [QualificationController::class, 'superadmin_qualification_transfer']);
            Route::post('save_document', [QualificationController::class, 'save_document']);
 
            //Submission
            Route::get('get_qualification_submissions', [QualificationController::class, 'get_qualification_submissions']);
            Route::get('get_qualification_submissions_V2', [QualificationController::class, 'get_qualification_submissions_V2']);
            Route::get('get_qualification_submissions_V3', [QualificationController::class, 'get_qualification_submissions_V3']);
            Route::get('get_submissions', [QualificationController::class, 'get_submissions']);
            Route::post('save_submission', [QualificationController::class, 'save_submission']);
            Route::post('delete_submission', [QualificationController::class, 'delete_submission']);

            Route::post('save_assessor_feedback', [QualificationController::class, 'save_assessor_feedback']);
            Route::get('get_assessor_feedback', [QualificationController::class, 'get_assessor_feedback']);
            
            Route::get('get_iqa_comment', [QualificationController::class, 'get_iqa_comment']);


            Route::post('update_submission_status', [QualificationController::class, 'update_submission_status']);
            Route::post('update_submission_iqa_status', [QualificationController::class, 'update_submission_iqa_status']);


            Route::post('update_document_detail', [QualificationController::class, 'update_document_detail']);

            Route::post('tt', [QualificationController::class, 'tt']);
        });

        Route::prefix('resource_materials')->group(static function (): void {
            Route::post('save_resource_materail', [ResourceMaterialController::class, 'save_resource_materail']);
            Route::post('edit_resource_materail', [ResourceMaterialController::class, 'edit_resource_materail']);
            Route::get('get_resource_materail', [ResourceMaterialController::class, 'get_resource_materail']);
            Route::delete('delete_resource_materail', [ResourceMaterialController::class, 'delete_resource_materail']);

            //IQA Report
            Route::post('save_iqa_report', [ResourceMaterialController::class, 'save_iqa_report']);
            Route::get('get_iqa_report', [ResourceMaterialController::class, 'get_iqa_report']);

            //Minutes of Meetings
            Route::post('save_minutes_of_meetings', [ResourceMaterialController::class, 'save_minutes_of_meetings']);
            Route::get('get_minutes_of_meetings', [ResourceMaterialController::class, 'get_minutes_of_meetings']);
        });

        Route::prefix('invoices')->group(static function (): void {
            Route::get('get_invoices', [InvoiceController::class, 'get_invoices']);
            Route::get('get_invoice_detail', [InvoiceController::class, 'get_invoice_detail']);
            Route::post('action_invoice_status', [InvoiceController::class, 'action_invoice_status']);
            Route::post('action_learner_status', [InvoiceController::class, 'action_learner_status']);
            // Route::post('action_learner_status', [InvoiceController::class, 'action_learner_status']);
        });
    });
});
