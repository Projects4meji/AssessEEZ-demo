<?php

namespace App\Http\Controllers\API;

use App\Http\Controllers\Controller;
use App\Http\Helpers\Helper;
use App\Http\Requests\RegisterRequest;
use App\Http\Resources\UserLoginResource;
use App\Http\Resources\UserResource;
use App\Mail\OtpMail;
use App\Mail\ResetPasswordLinkMail;
use App\Models\Otp;
use App\Models\PasswordResetToken;
use App\Models\Permission;
use App\Models\RolePermission;
use App\Models\SignupUser;
use App\Models\Status;
use App\Models\User;
use App\Models\UserRole;
use Carbon\Carbon;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Mail;
use Illuminate\Support\Facades\Validator;
use Illuminate\Support\Str;

class AuthController extends Controller
{
    public function sign_up(Request $request)
    {
        $verification_method = $request->verification_method;

        if ($verification_method == 1) {
            $validator = Validator::make($request->all(), [
                'name' => 'required|string|max:255',
                'email' => 'required|digits:11|unique:users,contact_no',
                'password' => 'required|string|min:8|confirmed',
            ], [
                'email.unique' => 'The contact number has already been taken.',
                'email.digits' => 'The contact number must be exactly 11 digits long.',
            ]);
        } else {
            $validator = Validator::make($request->all(), [
                'name' => 'required|string|max:255',
                'email' => 'required|string|email|max:255|unique:users,email',
                'password' => 'required|string|min:8|confirmed',
            ]);
        }

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        try {
            $userData = [
                'name' => $request->name,
                'password' => Hash::make($request->password),
            ];

            if ($request->verification_method == 1) {
                $userData['contact_no'] = $request->email;
            } else {
                $userData['email'] = $request->email;
            }

            User::create($userData);

            $otp_data = [
                'email' => $request->email,
                'verification_method' => $verification_method
            ];

            Helper::sendOtp($otp_data);

            $message = $verification_method == 1 ? 'contact number' : 'email';

            return response()->json([
                'message' => 'User registered successfully. Check your ' . $message . ' for the OTP.',
            ], 201);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Registration failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function resend_otp(Request $request)
    {
        try {
            $verification_method = $request->verification_method;

            if ($verification_method == 1) {
                $validator = Validator::make($request->all(), [
                    'email' => 'required|digits:11|unique:exists,contact_no',
                    'type' => 'required',
                ], [
                    'email.exists' => 'This contact number does not exist in our records. Please provide a valid contact number.',
                    'email.digits' => 'The contact number must be exactly 11 digits long.',
                ]);
            } else {
                $validator = Validator::make($request->all(), [
                    'email' => 'required|string|email|max:255|exists:users,email',
                    'type' => 'required',
                ], [
                    'email.exists' => 'This email does not exist in our records. Please provide a valid email.'
                ]);
            }

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            $user = User::where('email', $request->email)->first();

            if (!$user) {
                return response()->json([
                    'error' => 'User not found',
                ], 404);
            }

            $otp_data = [
                'email' => $request->email,
                'verification_method' => $verification_method
            ];

            if ($request->type == 'register') {
                Helper::sendOtp($otp_data);
            } elseif ($request->type == 'change_email') {
                Helper::sendEmailChange($otp_data);
            } elseif ($request->type == 'forgot_password') {
                Helper::sendForgotPassword($otp_data);
            } elseif ($request->type == 'account_delete') {
                Helper::sendOtp($otp_data);
            } else {
                return response()->json([
                    'error' => 'Type not found',
                ], 500);
            }

            $message = $verification_method == 1 ? 'contact number' : 'email';

            return response()->json([
                'message' => 'OTP sent successfully. Check your ' . $message . ' for the OTP.',
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Failed to send OTP',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function verify_otp(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'email' => 'required|string|max:255',
            'otp' => 'required|size:6',
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        try {
            $otpEntry = Otp::where('email', $request->email)
                ->where('otp', $request->otp)
                ->first();

            if (!$otpEntry) {
                return response()->json([
                    'error' => 'Invalid OTP',
                ], 401);
            }

            $otpEntry->delete();

            $user = User::where('email', $request->email)->first();

            if ($user) {
                $user->email_verified_at = Carbon::now();
                $user->save();
            }

            return response()->json([
                'message' => 'OTP verified successfully',
                'data' => new UserLoginResource($user),
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'OTP verification failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function login(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'email' => 'required|exists:users,email',
                'password' => 'required',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            $user = User::where('email', $request->email)->first();

            if ((int)$user->role_id > 2 && $user->status != "active") {
                return response()->json([
                    'error' => 'Your account is inactive! Please contact administrator.'
                ], 401);
            }

            $is_verified = $user->hasVerifiedEmail();

            if ($is_verified == false) {
                return response()->json([
                    'error' => 'Your account is not verified. Please verify your account'
                ], 401);
            }

            if (!$user || !Hash::check($request->password, $user->password)) {
                return response()->json([
                    'error' => 'Invalid credentials'
                ], 401);
            }

            $token = $user->createToken('auth_token')->plainTextToken;

            // user role
            $user_role = [];
            $path = null;

            if ($user != null && (int)$user->role_id == 1) {
                $user_role = UserRole::where('user_id', $user->id)->with('getRole.getPermission.getPermission.getPermissionType.getpermissionType')->get();

                $id_role = UserRole::where('user_id', $user->id)->first();
                $id_permission = RolePermission::where('role_id', $id_role->role_id)->pluck('permission_id');
                $path = Permission::whereIn('id', $id_permission)->orderBy('sequence_no', 'asc')->first();
            }

            return response()->json([
                'access_token' => $token,
                'token_type' => 'Bearer',
                'data' => new UserLoginResource($user),
                'user_role' => $user_role,
                'path' => $path != null ? $path->path : null
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Failed to Login',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function forgot_password(Request $request)
    {
        try {
            $verification_method = $request->verification_method;

            if ($verification_method == 1) {
                $validator = Validator::make($request->all(), [
                    'email' => 'required|digits:11|exists:users,contact_no',
                ], [
                    'email.exists' => 'This contact number does not exist in our records. Please provide a valid contact number.',
                    'email.digits' => 'The contact number must be exactly 11 digits long.',
                ]);
            } else {
                $validator = Validator::make($request->all(), [
                    'email' => 'required|string|email|max:255|exists:users,email',
                ]);
            }

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            $user = User::where('email', $request->email)->first();

            if (!$user) {
                return response()->json([
                    'error' => 'User not found',
                ], 404);
            }

            $is_verified = $user->hasVerifiedEmail();

            if ($is_verified == false) {
                return response()->json([
                    'error' => 'Your account is not verified. Please verify your account'
                ], 401);
            }

            $otp_data = [
                'email' => $request->email,
                'verification_method' => $verification_method
            ];

            Helper::sendForgotPassword($otp_data);

            $message = $verification_method == 1 ? 'contact number' : 'email';

            return response()->json([
                'message' => 'OTP sent successfully. Check your ' . $message . ' for the OTP.',
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Failed to send forgot password',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function verify_forgot_password(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'email' => 'required|string|max:255',
            'otp' => 'required|size:6',
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        try {
            $otpEntry = PasswordResetToken::where('email', $request->email)
                ->where('otp', $request->otp)
                ->first();

            if (!$otpEntry) {
                return response()->json([
                    'error' => 'Invalid OTP',
                ], 401);
            }

            $otpEntry->delete();

            return response()->json([
                'message' => 'OTP verified successfully',
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'OTP verification failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function change_forgot_password(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'email' => 'required|string',
                'password' => 'required|string|min:8|confirmed',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            $user = User::where('email', $request->email)->first();

            if (!$user) {
                return response()->json([
                    'error' => 'User not found',
                ], 404);
            }

            if (Hash::check($request->password, $user->password)) {
                return response()->json([
                    'error' => 'New password cannot be the same as the old password',
                ], 400);
            }

            $user->password = Hash::make($request->password);
            $user->save();

            return response()->json([
                'message' => 'Your password has been changed successfully',
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Failed to send OTP',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_user_statuses(Request $request)
    {
        $query = Status::where('type', 'user');

        if ($request->has('search')) {
            $searchTerm = $request->input('search');
            $query->where('name', 'like', "%$searchTerm%");
        }

        $statuses = $query->get();

        if ($statuses->isEmpty()) {
            return response()->json(['error' => 'No records found.'], 404);
        }

        return response()->json([
            'message' => 'Status',
            'data' => $statuses,
        ], 200);
    }

    public function send_reset_password_link(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'email' => 'required|string|email|max:255|exists:users,email',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            $user = User::where('email', $request->email)->first();

            if (!$user) {
                return response()->json([
                    'error' => 'User not found',
                ], 404);
            }

            if ($user) {
                $link = 'https://ezas.dotserviz.com/forgot';
                Mail::to($user->email)->send(new ResetPasswordLinkMail($link));
            }

            return response()->json([
                'message' => 'Sent successfully',
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }
}
