<?php

namespace App\Http\Controllers\API;

use App\Http\Controllers\Controller;
use App\Http\Helpers\Helper;
use App\Http\Resources\AssessorDocumenResource;
use App\Http\Resources\AssessorDocumenResource_V1;
use App\Http\Resources\AssessorResource;
use App\Http\Resources\RoleResource;
use App\Http\Resources\UserResource;
use App\Http\Resources\CommunicationResource;
use App\Http\Resources\CustomerResource;
use App\Http\Resources\UserDetailResource_V1;
use App\Http\Resources\UserDropdownResource_V1;
use App\Http\Resources\UserLoginResource;
use App\Http\Resources\UserNameResource;
use App\Http\Resources\UserResource_V1;
use App\Imports\LearnerImport;
use App\Imports\UsersImport;
use App\Mail\BulkEditUserMail;
use App\Models\AssessorDocument;
use App\Models\AssessorDocumentAttachement;
use App\Models\Communication;
use App\Models\Customer;
use App\Models\Order;
use App\Models\Otp;
use App\Models\Product;
use App\Models\Qualification;
use App\Models\QualificationAc;
use App\Models\QualificationDocument;
use App\Models\QualificationSubmission;
use App\Models\RequestPayment;
use App\Models\Role;
use App\Models\SubmissionAttachement;
use App\Models\Type;
use App\Models\UpdateUserDetailLog;
use App\Models\User;
use App\Models\UserAssessor;
use App\Models\UserIqa;
use App\Models\UserLearner;
use App\Models\UserQualification;
use App\Models\UserReference;
use App\Models\UserRole;
use Carbon\Carbon;
use Exception;
use GuzzleHttp\Client;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Mail;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Facades\URL;
use Illuminate\Support\Facades\Validator;
use Illuminate\Support\Str;
use Illuminate\Validation\Rule;
use Maatwebsite\Excel\Facades\Excel;

class UserController extends Controller
{
    public function update_profile(Request $request)
    {
        try {
            $user_id = $request->user_id ? $request->user_id : Auth::id();
            $user = User::where('id', $user_id)->first();

            if ($request->name) {
                $validator = Validator::make($request->all(), [
                    'name' => 'required|string|max:255',
                ]);

                if ($validator->fails()) {
                    $errors = $validator->errors()->all();
                    return response()->json([
                        'message' => 'Validation errors',
                        'error' => $errors[0]
                    ], 422);
                }

                $user->name = $request->name;
            }

            $user->contact_no = $request->contact_no ? $request->contact_no : null;
            $user->location = $request->location ? $request->location : null;
            $user->country = $request->country ? $request->country : null;
            $user->city = $request->city ? $request->city : null;
            $user->lat = $request->lat ? $request->lat : null;
            $user->lon = $request->lon ? $request->lon : null;
            $user->about_me = $request->about_me ? $request->about_me : null;
            $user->is_city_show = $request->is_city_show ? $request->is_city_show : 0;
            $user->save();

            if ($request->hasfile('avatar')) {
                $extension = $request->file('avatar')->extension();
                $avatar = $request->file('avatar');
                $url = Str::random(20) . '.' . $extension;
                
                $path = 'user_avatar/' . $url;
                Helper::FileUpload($path, $avatar);

                // Storage::disk('local')->put(
                //     '/public/user_avatar/' . $url,
                //     File::get($avatar)
                // );
                
                
                $user->avatar = $url;
                $user->save();
            }


            return response()->json([
                'message' => 'Profile updated successfully',
                'data' => new UserResource($user)
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Update failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function update_profile_picture(Request $request)
    {
        try {
            $user = User::where('id', Auth::id())->first();

            $validator = Validator::make($request->all(), [
                'avatar' => 'required|max:255',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            $extension = $request->file('avatar')->extension();
            $avatar = $request->file('avatar');
            $url = Str::random(20) . '.' . $extension;
            
            $path = 'user_avatar/' . $url;
            Helper::FileUpload($path, $avatar);
            // Storage::disk('local')->put(
            //     '/public/user_avatar/' . $url,
            //     File::get($avatar)
            // );
            $user->avatar = $url;
            $user->save();


            return response()->json([
                'message' => 'Profile updated successfully',
                'data' => new UserLoginResource($user)
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Update failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function change_email_otp(Request $request)
    {
        try {
            $user = User::where('id', Auth::id())->first();

            if (!$user) {
                return response()->json([
                    'error' => 'User not found',
                ], 404);
            }

            $otp_data = [
                'email' => $user->email ? $user->email : $user->contact_no,
                'verification_method' => $user->contact_no ? 1 : 0
            ];

            Helper::sendEmailChange($otp_data);

            $message = $user->contact_no ? 'contact number' : 'email';

            return response()->json([
                'message' => 'OTP sent successfully. Check your ' . $message . ' for the OTP.',
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Failed to send change email',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function change_email(Request $request)
    {
        try {
            $verification_method = $request->verification_method;

            if ($verification_method == 1) {
                $validator = Validator::make($request->all(), [
                    'email' => 'required|digits:11|unique:exists,contact_no',
                    'otp' => 'required|string|size:6',
                ], [
                    'email.exists' => 'This contact number does not exist in our records. Please provide a valid contact number.',
                    'email.digits' => 'The contact number must be exactly 11 digits long.',
                ]);
            } else {
                $validator = Validator::make($request->all(), [
                    'email' => 'required|string|email|max:255|exists:users,email',
                    'otp' => 'required|string|size:6',
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

            $user = User::where('id', Auth::id())->first();

            $otpEntry = Otp::where('email', $user->email)
                ->where('otp', $request->otp)
                ->first();

            if (!$otpEntry) {
                return response()->json([
                    'error' => 'Invalid OTP',
                ], 401);
            }

            $otpEntry->delete();

            $user = User::where('email', $user->email)->orWhere('email', $user->email)->first();

            if ($user) {
                if ($verification_method == 1) {
                    $user->contact_no = $request->email;
                } else {
                    $user->email = $request->email;
                }
                $user->save();
            }

            return response()->json([
                'message' => 'Email Changed Successfully',
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Failed to send change email',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function change_password(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'current_password' => 'required',
                'new_password' => 'required|string|min:8|confirmed',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            $user = User::where('id', Auth::id())->first();

            if (!$user) {
                return response()->json([
                    'error' => 'User not found',
                ], 404);
            }

            if (!Hash::check($request->current_password, $user->password)) {
                return response()->json([
                    'error' => 'Current password is incorrect',
                ], 400);
            }

            if (Hash::check($request->new_password, $user->password)) {
                return response()->json([
                    'error' => 'New password cannot be the same as the old password',
                ], 400);
            }

            $user->password = Hash::make($request->new_password);
            $user->save();

            return response()->json([
                'message' => 'Your password has been changed successfully',
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Failed changed password',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function change_password_by_admin(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'user_id' => 'required',
                'new_password' => 'required|string|min:8|confirmed',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            $user = User::where('id', $request->user_id)->first();

            if (!$user) {
                return response()->json([
                    'error' => 'User not found',
                ], 404);
            }

            if (Hash::check($request->new_password, $user->password)) {
                return response()->json([
                    'error' => 'New password cannot be the same as the old password',
                ], 400);
            }

            $user->password = Hash::make($request->new_password);
            $user->save();

            return response()->json([
                'message' => 'Password has been changed successfully',
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Failed changed password',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function delete_account(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'otp' => 'required',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'errors' => $errors[0]
                ], 422);
            }

            $user = Auth::user();


            $otpEntry = Otp::where('email', $user->email)
                ->where('otp', $request->otp)
                ->first();

            if (!$otpEntry) {
                return response()->json([
                    'error' => 'Invalid OTP',
                ], 401);
            }

            $otpEntry->delete();

            User::where('email', $user->email)->delete();

            return response()->json(['message' => 'User account deleted successfully.'], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Failed delete account',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function action_user_status(Request $request)
    {
        try {

            $validator = Validator::make($request->all(), [
                'id' => 'required',
                'status' => 'required',
                // 'qualification_id' => 'required',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            $user = User::where('id', $request->id)->whereNotIn('role_id', [1, 2])->first();

            if ((int)$user->role_id == 3 && $request->qualification_id == null) {
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => 'The user qualification id field is required.',
                ], 422);
            }

            if ($user != null) {
                if ($request->status == 'deleted') {
                    // User::where('id', $request->id)->delete();
                    // QualificationSubmission::where('created_by', $request->id)->delete();
                    // QualificationDocument::where('created_by', $request->id)->delete();
                    // UserQualification::where('user_id', $request->id)->delete();
                    // UserAssessor::where('user_id', $request->id)->delete();
                    // UserIqa::where('user_id', $request->id)->delete();
                    if ((int)$user->role_id == 3) {
                        QualificationSubmission::where('created_by', $request->id)->where('qualification_id', $request->qualification_id)->delete();
                        SubmissionAttachement::where('created_by', $request->id)->where('qualification_id', $request->qualification_id)->delete();
                        QualificationDocument::where('created_by', $request->id)->where('qualification_id', $request->qualification_id)->delete();
                        UserAssessor::where('user_id', $request->id)->where('qualification_id', $request->qualification_id)->delete();
                        UserIqa::where('user_id', $request->id)->where('qualification_id', $request->qualification_id)->delete();
                        UserQualification::where('user_id', $request->id)->where('qualification_id', $request->qualification_id)->delete();

                        $userQualification_ = UserQualification::where('user_id', $request->id)->count();
                        if((int)$userQualification_ == 0) {
                            User::where('id', $request->id)->delete();
                        }
                    } else {

                        $userQualificationList_ = UserQualification::where('user_id', $request->id)->get();
                        foreach($userQualificationList_ as $quali_) {
                            //Assessor Case
                            if((int)$user->role_id == 4) {
                                //Get All User Ids From User Assessor's qualification
                                $userAssessorWithQualifications = UserAssessor::where('assessor_id', $request->id)
                                ->where('qualification_id', $quali_->qualification_id)->withTrashed()->count();

                                if((int)$userAssessorWithQualifications > 0) {
                                    $qualificationTitle = Qualification::where('id', $quali_->qualification_id)->withTrashed()->first();

                                    return response()->json([
                                        'message' => 'Validation errors',
                                        'error' => 'The qualification (' . ($qualificationTitle != null ? $qualificationTitle->sub_title : "") . ') has assigned learners. Please assign a different assessor to the learners first'
                                    ], 422); 
                                }
                            } else if ((int)$user->role_id == 5) {
                                //Get All User Ids From User IQA's qualification
                                $userIQAWithQualifications = UserIqa::where('iqa_id', $request->id)
                                ->where('qualification_id', $quali_->qualification_id)->withTrashed()->count();

                                if((int)$$userIQAWithQualifications > 0) {
                                    $qualificationTitle = Qualification::where('id', $quali_->qualification_id)->withTrashed()->first();

                                    return response()->json([
                                        'message' => 'Validation errors',
                                        'error' => 'The qualification (' . ($qualificationTitle != null ? $qualificationTitle->sub_title : "") . ') has assigned learners. Please assign a different iqa to the learners first'
                                    ], 422); 
                                }
                            }                            
                        }

                        QualificationDocument::where('created_by', $request->id)->delete();
                        if((int)$user->role_id == 4) {
                            UserAssessor::where('assessor_id', $request->id)->delete();
                        } else if ((int)$user->role_id == 5) {
                            UserIqa::where('iqa_id', $request->id)->delete();
                        }
                        DB::table('user_qualifications')->where('user_id', $request->id)->delete();
                        User::where('id', $request->id)->delete();
                    }                    
                } else {

                    $status_ = ($request->status == "de_active" ? "inactive" : $request->status);
                    // switch($request->status) {
                    //     case "de_active":
                    //     case "inActive":
                    //         $status_ = "inactive";
                    //         break;
                    //     case "Active":
                    //         $status_ = "active";
                    //         break;
                    //     default:
                    //         $status_ = $request->status;
                    //     break;
                    // }

                    if((int)$user->role_id == 3) {

                        $updateUserQualification = UserQualification::where('user_id', $request->id)
                        ->where('qualification_id', $request->qualification_id)->first();

                        if($updateUserQualification != null) {
                            $updateUserQualification->status = $status_;
                            $updateUserQualification->save();
                        }
                        
                        $userQualification_ = UserQualification::where('user_id', $request->id)->where('status','active')->count();
                        if((int)$userQualification_ == 0) {
                            $user->status = $status_;
                            $user->save();
                        }
                    } else {

                        UserQualification::where('user_id', $request->id)->update(['status' => $status_]);
                        
                        $user->status = $status_;
                        $user->save();
                    }                    
                }                
            } else {
                return response()->json([
                    'message' => 'Failed to change',
                    'error' => 'User not found',
                ], 500);
            }

            return response()->json([
                'message' => 'User ' . $request->status . ' Successfully',
                'data' => new UserResource($user)
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Failed to change',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function update_user_address(Request $request)
    {
        try {
            $user = User::where('id', Auth::id())->first();

            $user->location = $request->location ? $request->location : null;
            $user->country = $request->country ? $request->country : null;
            $user->city = $request->city ? $request->city : null;
            $user->lat = $request->lat ? $request->lat : null;
            $user->lon = $request->lon ? $request->lon : null;
            $user->save();

            return response()->json([
                'message' => 'User address updated successfully',
                'data' => new UserResource($user)
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Update failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function update_payment_method(Request $request)
    {
        try {
            $user = User::where('id', Auth::id())->first();

            $user->payment_method = $request->payment_method ? $request->payment_method : null;
            $user->save();

            return response()->json([
                'message' => 'User payment method updated successfully',
                'data' => new UserResource($user)
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Update failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_places(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'place_id' => 'required',
        ]);

        if ($validator->fails()) {
            $response_data = [
                'success' => false,
                'message' => 'Incomplete data provided!',
                'errors' => $validator->errors(),
            ];
            return response()->json($response_data);
        }

        $client = new Client();
        $url = 'https://maps.googleapis.com/maps/api/place/details/json';
        $apiKey = 'AIzaSyCfkkFnJ7ixENdtACx3-Q5Mewh3wftkCo8';

        $response = $client->get($url, [
            'query' => [
                'place_id' => $request->place_id,
                'key' => $apiKey,
            ],
        ]);

        $data = json_decode($response->getBody(), true);
        return $data;
    }

    public function admin_dashboard(Request $request)
    {
        $users = User::where('status', 'active')->count();
        $orders = Order::where('status', 'completed')->count();
        $refunds = 0;
        $earnings = 0;
        $products = Product::count();
        $withdraw_request = RequestPayment::where('status', 'approved')->count();

        return response()->json([
            'message' => 'admin dashboard',
            'data' => [
                'users' => $users,
                'orders' => $orders,
                'refunds' => $refunds,
                'earnings' => $earnings,
                'products' => $products,
                'withdraw_request' => $withdraw_request,
            ]
        ], 200);
    }

    public function get_assessors_list(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'company_admin_id' => 'required',
        ]);

        if ($validator->fails()) {
            return response()->json([
                'message' => 'Validation errors',
                'error' => $validator->errors()->first(),
            ], 422);
        }
        
        $data = User::where('role_id', 4)->whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id))->pluck('id');        
        $userQualificationData = UserQualification::whereIn('user_id', $data);

        if($request->has('iqa_id')) {
            $iqa_qualification = UserQualification::where('user_id', $request->iqa_id)->pluck('qualification_id');
            $user_iqa = UserIqa::where('iqa_id', $request->iqa_id)->whereIn('qualification_id', $iqa_qualification)->pluck('user_id');

            $assessors_ = UserAssessor::whereIn('user_id', $user_iqa)->whereIn('qualification_id', $iqa_qualification)->pluck('assessor_id');
            $userQualificationData->whereIn('user_id', $assessors_);
        }       

        $count = $userQualificationData->count();

        if ($request->has('page')) {
            $assessors = $userQualificationData->paginate(20);
        } else {
            $assessors = $userQualificationData->get();
        }

        if ($assessors->isEmpty()) {
            return response()->json(['error' => 'No assessors found.'], 404);
        }

        return response()->json([
            'message' => 'Assessors',
            'data' => AssessorResource::collection($assessors),
            'count' => $count
        ], 200);
    }

    public function get_assessors(Request $request)
    {
        $query = User::where('role_id', 4);

        if ($request->has('qualification_id')) {
            $userQualificationInfo = UserQualification::where('qualification_id', $request->qualification_id)->pluck('user_id');

            if($request->has('iqa_id')) {
                $iqaUsers = UserIqa::where('qualification_id', $request->qualification_id)->where('iqa_id', $request->iqa_id)->pluck('user_id');
                $assessers_ = UserAssessor::where('qualification_id', $request->qualification_id)->whereIn('user_id', $iqaUsers)->pluck('assessor_id');

                $query->whereIn('id', $assessers_);    
            }

            $query->whereIn('id', $userQualificationInfo);
        }

        if ($request->has('user_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->user_id));
        }

        if ($request->has('company_admin_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id));
        }

        // if ($request->has('search')) {
        //     $searchTerm = $request->input('search');
        //     $query->where('name', 'like', "%$searchTerm%");
        // }

        $count = $query->count();

        if ($request->has('page')) {
            $assessors = $query->paginate(20);
        } else {
            $assessors = $query->get();
        }

        if ($assessors->isEmpty()) {
            return response()->json(['error' => 'No assessors found.'], 404);
        }

        return response()->json([
            'message' => 'Assessors',
            'data' => UserResource::collection($assessors),
            'count' => $count
        ], 200);
    }

    public function get_assessorsV1(Request $request)
    {
        $query = User::where('role_id', 4);

        if ($request->has('qualification_id')) {
            $userQualificationInfo = UserQualification::where('qualification_id', $request->qualification_id)->pluck('user_id');
            $query->whereIn('id', $userQualificationInfo);
        }

        if ($request->has('user_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->user_id));
        }

        if ($request->has('company_admin_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id));
        }

        // $count = $query->count();

        // if ($request->has('page')) {
        //     $assessors = $query->paginate(20);
        // } else {
        //     $assessors = $query->get();
        // }

        if($request->isEdit && $request->isEdit == "true") {
            $assessors = $query->withTrashed()->get();
        } else {
            $assessors = $query->get();
        }

        if ($assessors->isEmpty()) {
            return response()->json(['error' => 'No assessors found.'], 404);
        }

        return response()->json([
            'message' => 'Assessors',
            'data' => UserResource::collection($assessors),
        ], 200);
    }

    public function get_assessorsV2(Request $request)
    {
        $query = User::where('role_id', 4);

        if ($request->has('qualification_id')) {
            $userQualificationInfo = UserQualification::where('qualification_id', $request->qualification_id)->pluck('user_id');
            $query->whereIn('id', $userQualificationInfo);
        }

        if ($request->has('user_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->user_id));
        }

        if ($request->has('company_admin_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id));
        }
        
        if($request->isEdit && $request->isEdit == "true") {
            $assessors = $query->withTrashed()->get();
        } else {
            $assessors = $query->get();
        }

        if ($assessors->isEmpty()) {
            return response()->json(['error' => 'No assessors found.'], 404);
        }

        return response()->json([
            'message' => 'Assessors',
            'data' => UserDropdownResource_V1::collection($assessors),
        ], 200);
    }

    public function get_iqas(Request $request)
    {
        $query = User::where('role_id', 5);

        if ($request->has('qualification_id')) {
            $userQualificationInfo = UserQualification::where('qualification_id', $request->qualification_id)->pluck('user_id');
            $query->whereIn('id', $userQualificationInfo);
        }

        if ($request->has('user_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->user_id));
        }

        if ($request->has('company_admin_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id));
        }

        // if ($request->has('search')) {
        //     $searchTerm = $request->input('search');
        //     $query->where('name', 'like', "%$searchTerm%");
        // }

        $count = $query->count();

        if ($request->has('page')) {
            $iqas = $query->paginate(20);
        } else {
            $iqas = $query->get();
        }

        if ($iqas->isEmpty()) {
            return response()->json(['error' => 'No iqas found.'], 404);
        }

        return response()->json([
            'message' => 'Iqas',
            'data' => UserResource::collection($iqas),
            'count' => $count
        ], 200);
    }

    public function get_iqasV1(Request $request)
    {
        $query = User::where('role_id', 5);

        if ($request->has('qualification_id')) {
            $userQualificationInfo = UserQualification::where('qualification_id', $request->qualification_id)->pluck('user_id');
            $query->whereIn('id', $userQualificationInfo);
        }

        if ($request->has('user_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->user_id));
        }

        if ($request->has('company_admin_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id));
        }

        // $count = $query->count();

        // if ($request->has('page')) {
        //     $iqas = $query->paginate(20);
        // } else {
        //     $iqas = $query->get();
        // }

        if($request->isEdit && $request->isEdit == "true") {
            $iqas = $query->withTrashed()->get();
        } else {
            $iqas = $query->get();
        }

        if ($iqas->isEmpty()) {
            return response()->json(['error' => 'No iqas found.'], 404);
        }

        return response()->json([
            'message' => 'Iqas',
            'data' => UserResource::collection($iqas),            
        ], 200);
    }

    public function get_iqasV2(Request $request)
    {
        $query = User::where('role_id', 5);

        if ($request->has('qualification_id')) {
            $userQualificationInfo = UserQualification::where('qualification_id', $request->qualification_id)->pluck('user_id');
            $query->whereIn('id', $userQualificationInfo);
        }

        if ($request->has('user_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->user_id));
        }

        if ($request->has('company_admin_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id));
        }

        if($request->isEdit && $request->isEdit == "true") {
            $iqas = $query->withTrashed()->get();
        } else {
            $iqas = $query->get();
        }

        if ($iqas->isEmpty()) {
            return response()->json(['error' => 'No iqas found.'], 404);
        }

        return response()->json([
            'message' => 'Iqas',
            'data' => UserDropdownResource_V1::collection($iqas),
        ], 200);
    }

    public function get_references(Request $request)
    {
        $subQuery = User::select('id')->where('role_id', 3);

        // $resourse_materials = $resourse_materials->where('created_by', Auth::id())
        // ->whereNull('folder_id')
        // ->select('created_by', 'folder_name', 'id', DB::raw(($request->id != null && $request->folder_id != null ? $request->id : 0) . ' as child_id'))
        // ->distinct('created_by', 'folder_name', 'id')->get();


        if ($request->has('user_id')) {
            $subQuery->whereIn('created_by', Helper::getAdmin_ids($request->user_id));
        }

        if ($request->has('company_admin_id')) {
            $subQuery->whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id));
        }

        $subQuery->distinct('id');

        $count = $subQuery->count();

        $query = User::whereIn('id', $subQuery->pluck('id'));

        if ($request->has('page')) {
            $references = $query->paginate(20);
        } else {
            $references = $query->get();
        }

        if ($references->isEmpty()) {
            return response()->json(['error' => 'No references found.'], 404);
        }

        return response()->json([
            'message' => 'References',
            'data' => UserResource::collection($references),
            'count' => $count
        ], 200);
    }

    public function get_types(Request $request)
    {
        $query = Type::query();

        if ($request->has('type')) {
            $type = $request->input('type');
            $query->where('type', $type);
        }

        // if ($request->has('search')) {
        //     $searchTerm = $request->input('search');
        //     $query->where('name', 'like', "%$searchTerm%");
        // }

        $count = $query->count();

        if ($request->has('page')) {
            $types = $query->paginate(20);
        } else {
            $types = $query->get();
        }

        if ($types->isEmpty()) {
            return response()->json(['error' => 'No types found.'], 404);
        }

        return response()->json([
            'message' => 'Types',
            'data' => $types,
            'count' => $count
        ], 200);
    }

    public function get_learners(Request $request)
    {
        $query = User::where('role_id', 3);

        if ($request->has('user_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->user_id));
        }

        if ($request->has('company_admin_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id));
        }

        if ($request->has('qualification_id')) {
            $userQualificationIds = UserQualification::where('qualification_id', $request->qualification_id)
            ->whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id))->pluck('user_id');
            $query->whereIn('id', $userQualificationIds);

            if($request->has('iqa_id')) {
                $iqaUsers = UserIqa::where('qualification_id', $request->qualification_id)->where('iqa_id', $request->iqa_id)->withTrashed()->pluck('user_id');
                // $assessers_ = UserAssessor::where('qualification_id', $request->qualification_id)->whereIn('user_id', $iqaUsers)->pluck('assessor_id');

                $query->whereIn('id', $iqaUsers);
            }
        }

        if($request->has('qualifications')) {
            $qualifications = json_decode($request->qualifications, true);
            
            // $qualification_ids_ = [];

            // foreach($qualifications as $qualific_) {
            //     $qualification_ids_[] = $qualific_["id"];
            // }

            // if (count($qualification_ids_) > 0) {
                $learners_qualifications_ = UserQualification::whereIn('qualification_id', $qualifications)->pluck('user_id');
                $query->whereIn('id', $learners_qualifications_);
            // }
        }


        if ($request->has('ref_number')) {
            $ref_number = $request->input('ref_number');
            $query->where('ref_number', $ref_number);
        }

        // if ($request->has('search')) {
        //     $searchTerm = $request->input('search');
        //     $query->where('name', 'like', "%$searchTerm%");
        // }

        $count = $query->count();

        if ($request->has('page')) {
            $learner = $query->paginate(20);
        } else {
            $learner = $query->get();
        }

        if ($learner->isEmpty()) {
            return response()->json(['error' => 'No learners found.'], 404);
        }

        return response()->json([
            'message' => 'Learners',
            // 'data' => UserResource::collection($learner),
            'data' => UserDropdownResource_V1::collection($learner),
            'count' => $count
        ], 200);
    }

    public function create_user(Request $request)
    {
        // $accountStatus = Auth::user();
        $auth_ = Auth::user();
        
        if($auth_->role_id != "2" && $auth_->role_id != "6") {
            return response()->json([
                'error' => 'Only admin can create user!'
            ], 422);
        }
        
        if($auth_->status != "active")
        {
            return response()->json([
                'error' => 'You account currenly inactive! Please contact administrator.'
            ], 422);
        }

        $validator = null;
        if ($request->role_id != null && (int)$request->role_id == 3) {
            $validator = Validator::make($request->all(), [
                'role_id' => 'required',
                'sur_name' => 'required|string|max:255',
                'qualifications' => 'required',
                'assessors' => 'required',
                'iqas' => 'required',
                'email' => 'required|string|email|max:255',
                'user_qualification_id' => 'required'
            ]);
        } else if ($request->role_id != null && (int)$request->role_id == 7) {
            $validator = Validator::make($request->all(), [
                'role_id' => 'required',
                'sur_name' => 'required|string|max:255',
                'qualifications' => 'required',
                'email' => 'required|string|email|max:255',
            ]);
        } else if ((int)$request->role_id == 6) {
            $validator = Validator::make($request->all(), [
                'role_id' => 'required',
                'sur_name' => 'required|string|max:255',
                'email' => 'required|string|email|max:255',
            ]);
        } else {
            $validator = Validator::make($request->all(), [
                'role_id' => 'required',
                'sur_name' => 'required|string|max:255',
                'qualifications' => 'required',
                'email' => 'required|string|email|max:255',
            ]);
        }

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        if ($request->id) {
            try {
                
                $user = User::where('id', $request->id)->first();
                if($user == null) {
                    return response()->json([
                        'message' => 'Validation errors',
                        'error' => 'User not found.'
                    ], 422);
                }
                
                $touqeer = null;

                $oldEmailRecord = $user->email;
                $oldUserQualificationData = [];
                $new_user_qualification_lear = [];
                $new_user_qualification_Assess = [];
                $new_user_qualification_IQA = [];
                $deleteLearnerUserQuali_ = false;

                $deleteAssessorUserQuali_ = false;
                $deleteIQAUserQuali_ = false;

                $alreadyExistEmail = User::where('email', $request->email)->where('id', '!=', $request->id)->first();
                if($alreadyExistEmail != null) {
                    return response()->json([
                        'message' => 'Validation errors',
                        'error' => 'This email already in use.'
                    ], 422);
                }

                // Fetch qualifications while excluding current user's qualifications
                $qualifications = $request->qualifications ? json_decode($request->qualifications, true) : [];
                // $existingUser = User::where('email', $request->email)->where('id', '!=', $request->id)->pluck('id');
                // if ($existingUser) {

                if($request->role_id == 3) {

                    $checkUserQualificationExist_ = UserQualification::where('id', $request->user_qualification_id)->first();
                    if($checkUserQualificationExist_ == null) {
                        return response()->json([
                            'message' => 'Validation errors',
                            'error' => 'User qualification not found!'
                        ], 422);
                    }

                    $existingQualifications = UserQualification::where('user_id', $request->id)->where('id', '!=', $request->user_qualification_id)
                    ->pluck('qualification_id')
                    ->toArray();

                    $newQualifications = array_column($qualifications, 'id');

                    if (array_intersect($newQualifications, $existingQualifications)) {
                        return response()->json([
                            'message' => 'Validation errors',
                            'error' => 'You are already registered with this email and qualifications'
                        ], 422);
                    }
                } else if ($request->role_id == 4 || $request->role_id == 5) {
                        $userQualificationList_ = UserQualification::where('user_id', $user->id)->get();
                        foreach($userQualificationList_ as $quali_) {
                            //Get All Qualification Ids
                            $qualificationCount = UserQualification::where('id', $quali_->id)
                            ->pluck('qualification_id')
                            ->toArray();

                            $qualificationArray = array_column($qualifications, 'id');
                            
                            //Any Assessor Qualification From Existing
                            if (!array_intersect($qualificationArray, $qualificationCount)) {
                                //Assessor Case
                                if($request->role_id == 4) {
                                    //Get All User Ids From User Assessor's qualification
                                    $userAssessorWithQualifications = UserAssessor::where('assessor_id', $user->id)
                                    ->where('qualification_id', $quali_->qualification_id)->withTrashed()->count();

                                    if((int)$userAssessorWithQualifications > 0) {
                                        $qualificationTitle = Qualification::where('id', $quali_->qualification_id)->withTrashed()->first();

                                        return response()->json([
                                            'message' => 'Validation errors',
                                            'error' => 'The qualification (' . ($qualificationTitle != null ? $qualificationTitle->sub_title : "") . ') has assigned learners. Please assign a different assessor to the learners first'
                                        ], 422); 
                                    }
                                } else if ($request->role_id == 5) {
                                    //Get All User Ids From User IQA's qualification
                                    $userIQAWithQualifications = UserIqa::where('iqa_id', $user->id)
                                    ->where('qualification_id', $quali_->qualification_id)->withTrashed()->count();

                                    if((int)$$userIQAWithQualifications > 0) {
                                        $qualificationTitle = Qualification::where('id', $quali_->qualification_id)->withTrashed()->first();

                                        return response()->json([
                                            'message' => 'Validation errors',
                                            'error' => 'The qualification (' . ($qualificationTitle != null ? $qualificationTitle->sub_title : "") . ') has assigned learners. Please assign a different iqa to the learners first'
                                        ], 422); 
                                    }
                                }
                            } 
                        }
                }


                
                // }

                $user->email = $request->email != null ? $request->email : $user->email;
                if($request->role_id == 6) {
                    $user->first_name = $request->first_name != null ? $request->first_name : $user->first_name;
                    $user->middle_name = $request->middle_name != null ? $request->middle_name : $user->middle_name;
                    $user->sur_name = $request->sur_name != null ? $request->sur_name : $user->sur_name;
                    $user->contact = $request->contact != null ? $request->contact : $user->contact;
                }
                ///// $user->role_id = $request->role_id ?? null;
                $user->save();

                $deleted_qualification_ids = [];

                if ($request->qualifications != null) {
                    $qualifications = json_decode($request->qualifications, true);
                    if($request->role_id == 3) {
                        $exUserQualification_ = UserQualification::where('id', $request->user_qualification_id)->first();

                        if($exUserQualification_ != null) {
                            
                            //Backup Data User Qualification 
                            $oldUserQualificationDataRec = UserQualification::where('id', $request->user_qualification_id)->first();
                            $oldUserQualificationData[] = $oldUserQualificationDataRec;
                            
                            $userSubmission = QualificationSubmission::where('created_by', $request->id)
                            ->where('qualification_id', $exUserQualification_->qualification_id)->count();

                            if($exUserQualification_->qualification_id != $qualifications[0]["id"] && $userSubmission > 0) {
                                
                                $user__ = User::where('id', $request->id)->first();
                                $user__->email = $oldEmailRecord;
                                $user__->save();

                                return response()->json([
                                    'message' => 'Validation errors',
                                    'error' => 'You cannot change qualification! Assessment submited in the current qualification.'
                                ], 422);
                            }
                        }

                            DB::table('user_qualifications')->where('id', $request->user_qualification_id)->delete();
                            $deleteLearnerUserQuali_ = true;

                            $qualification_recordN = [
                                'user_id' => $user ? $user->id : 0,
                                'qualification_id' => $qualifications[0]['id'],
                                'status' => 'active',
                                'created_by' => Auth::id(),
                                'updated_by' => Auth::id(),
                            ];
    
                            $user_qualificationNew = UserQualification::create($qualification_recordN);
                            $user_qualificationNew->ref_number = $request->ref_number ?? null;
                            $user_qualificationNew->first_name = $request->first_name ?? null;
                            $user_qualificationNew->middle_name = $request->middle_name ?? null;
                            $user_qualificationNew->sur_name = $request->sur_name ?? null;
                            $user_qualificationNew->learner_number = $request->learner_number ?? null;
                            $user_qualificationNew->date_of_registration = $request->date_of_registration ?? null;
                            $user_qualificationNew->cohort_batch_no = $request->cohort_batch_no ?? null;
                            $user_qualificationNew->contact = $request->contact ?? null;                            
                            $user_qualificationNew->date_of_birth = $request->date_of_birth ?? null;
                            $user_qualificationNew->disability = ($request->role_id == 3 ? ($request->disability == "yes" ? true : false) : false);                                                        
                            $user_qualificationNew->location = $request->location ?? null;
                            $user_qualificationNew->country = $request->country ?? null;
                            $user_qualificationNew->city = $request->city ?? null;
                            $user_qualificationNew->lat = $request->lat ?? null;
                            $user_qualificationNew->lon = $request->lon ?? null;                            
                            $user_qualificationNew->save();
    
                            $new_user_qualification_lear[] = $user_qualificationNew->id;
                        
                    } else {                        
                        //region commit Code
                        /*
                        foreach($userQualificationList_ as $quali_) {
                            
                            //Get All Qualification Ids
                            $qualificationCount = UserQualification::where('id', $quali_->id)
                            ->pluck('qualification_id')
                            ->toArray();

                            $qualificationArray = array_column($qualifications, 'id');
                            
                            //Any Assessor Qualification From Existing
                            if (!array_intersect($qualificationArray, $qualificationCount)) {
                                //Assessor Case
                                if($request->user_role == 4) {
                                    //Get All User Ids From User Assessor's removal qualification
                                    $userAssessorWithQualifications = UserAssessor::where('assessor_id', $user->id)
                                    ->where('qualification_id', $quali_->qualification_id)->pluck('user_id');

                                    //Get All Assessments of removal qualification
                                    $assessments = QualificationAc::where('qualification_id', $quali_->qualification_id)->pluck('id');
                                    
                                    //Find Submissions of removal qualication with respect of assessor
                                    foreach($userAssessorWithQualifications as $user_assessors_) {
                                        
                                        //Qualification Submission count of current user
                                        $submissionCount_ = QualificationSubmission::where('created_by', $user_assessors_)
                                            ->where('qualification_id', $quali_->qualification_id)
                                            ->whereIn('ac_id', $assessments);
                                        
                                        //Qualification Accept records count
                                        $completedSubmissions = $submissionCount_->where('status', 'Accept')->count();

                                        //check all assessment submission count
                                        if(($submissionCount_->count() < $assessments->count()) || ($completedSubmissions < $assessments->count())) {

                                            $qualificationTitle = Qualification::where('id', $quali_->qualification_id)->withTrashed()->first();

                                            return response()->json([
                                                'message' => 'Validation errors',
                                                'error' => 'The qualification (' . ($qualificationTitle != null ? $qualificationTitle->sub_title : "") . ') has pending assessments for its learners. Please assign a different assessor to the learners first'
                                            ], 422);
                                        } else {
                                            // UserQualification::where('user_id', $user->id)->where('qualification_id', $quali_->qualification_id)->delete();
                                            $userQuali_ = UserQualification::where('user_id', $user->id)->where('qualification_id', $quali_->qualification_id)->first();
                                            
                                            if($userQuali_ != null) {
                                                $deleted_qualification_ids[] = $userQuali_->id;
                                            }
                                        }
                                    }
                                } else if ($request->user_role == 5) {
                                    //Get All User Ids From User IQA's removal qualification
                                    $userIQAWithQualifications = UserIqa::where('iqa_id', $user->id)
                                    ->where('qualification_id', $quali_->qualification_id)->pluck('user_id');

                                    //Get All Assessments of removal qualification
                                    $assessments = QualificationAc::where('qualification_id', $quali_->qualification_id)->pluck('id');

                                    //Find Submissions of removal qualication with respect of iqa
                                    foreach($userIQAWithQualifications as $user_iqa_) {
                                        
                                        //Qualification Submission count of current user
                                        $submissionCount_ = QualificationSubmission::where('created_by', $user_iqa_)
                                            ->where('qualification_id', $quali_->qualification_id)
                                            ->whereIn('ac_id', $assessments);
                                        
                                        //Qualification Accept records count
                                        $completedSubmissions = $submissionCount_->where('status', 'Accept')->count();

                                        //check all assessment submission count
                                        if(($submissionCount_->count() < $assessments->count()) || ($completedSubmissions < $assessments->count())) {

                                            $qualificationTitle = Qualification::where('id', $quali_->qualification_id)->withTrashed()->first();

                                            return response()->json([
                                                'message' => 'Validation errors',
                                                'error' => 'The qualification (' . ($qualificationTitle != null ? $qualificationTitle->sub_title : "") . ') has pending assessments for its learners. Please assign a different iqa to the learners first'
                                            ], 422);
                                        } else {
                                            // UserQualification::where('user_id', $user->id)->where('qualification_id', $quali_->qualification_id)->delete();
                                            $userQuali_ = UserQualification::where('user_id', $user->id)->where('qualification_id', $quali_->qualification_id)->first();
                                            
                                            if($userQuali_ != null) {
                                                $deleted_qualification_ids[] = $userQuali_->id;
                                            }

                                        }
                                    }
                                }
                            } else {
                                
                            }
                        }
                        */
                        //endregion 
                        if ($request->role_id == 4 || $request->role_id == 5 || $request->role_id == 7) {

                            foreach($qualifications as $currQualification_) { 
                                $oldUserQualificationDataRec = UserQualification::where('user_id', $user->id)
                                ->where('qualification_id', $currQualification_['id'])->first();

                                $oldUserQualificationData[] = $oldUserQualificationDataRec;
                            }
                            

                            DB::table('user_qualifications')->where('user_id', $user->id)->delete();
                            $deleteAssessorUserQuali_ = true;
    
                            foreach($qualifications as $currQualification) {
                                $qualificationAssessor_recordN = [
                                    'user_id' => $user ? $user->id : 0,
                                    'qualification_id' => $currQualification['id'],
                                    'first_name' => $request->first_name ?? null,
                                    'middle_name' => $request->middle_name ?? null,
                                    'sur_name' => $request->sur_name ?? null,
                                    'contact' => $request->contact ?? null,
                                    'status' => 'active',
                                    'created_by' => Auth::id(),
                                    'updated_by' => Auth::id(),
                                ];
        
                                $user_qualificationAssessrNew = UserQualification::create($qualificationAssessor_recordN);
                                $new_user_qualification_Assess[] = $user_qualificationAssessrNew->id;
                            }
                        }                        
                    }
                } 
                

                //Temporary Useles
                // if (($request->role_id != 3 && $request->role_id != 4 && $request->role_id != 5) && $request->qualifications != null) {
                //     UserQualification::where('user_id', $user->id)->delete();
                    
                    
                                                            
                //     $qualifications = json_decode($request->qualifications, true);

                //     foreach ($qualifications as $qualification) {

                //         $userQualification_ = UserQualification::where('');

                //         $qualification_record = [
                //             'user_id' => $user ? $user->id : 0,
                //             'qualification_id' => $qualification['id'],
                //             'created_by' => Auth::id(),
                //             'updated_by' => Auth::id(),
                //         ];

                //         $user_qualification = UserQualification::create($qualification_record);
                //         $user_qualification->ref_number = $request->ref_number ?? null;
                //         $user_qualification->contact = $request->contact ?? null;
                //         $user_qualification->date_of_birth = $request->date_of_birth ?? null;
                //         $user_qualification->cohort_batch_no = $request->cohort_batch_no ?? null;
                //         $user_qualification->date_of_registration = $request->date_of_registration ?? null;
                //         $user_qualification->sampling_ratio = $request->sampling_ratio ?? null;
                //         $user_qualification->view_only_id = $request->view_only_id ?? null;
                //         $user_qualification->learner_number = $request->learner_number ?? null;
                //         $user_qualification->location = $request->location ?? null;
                //         $user_qualification->country = $request->country ?? null;
                //         $user_qualification->city = $request->city ?? null;
                //         $user_qualification->lat = $request->lat ?? null;
                //         $user_qualification->lon = $request->lon ?? null;
                //         $user_qualification->expiry_date = $request->expiry_date ?? null;
                //         $user_qualification->first_name = $request->first_name ?? null;
                //         $user_qualification->middle_name = $request->middle_name ?? null;
                //         $user_qualification->sur_name = $request->sur_name ?? null;
                //         $user_qualification->disability = ($request->role_id == 3 ? ($request->disability == "yes" ? true : false) : false);
                //         $user_qualification->save();
                //     }
                // }

                if($request->role_id == 3) {
                    if ($request->assessors != null) {

                        $assessors = json_decode($request->assessors, true);

                        $existAssessors_ = UserAssessor::where('user_id', $user->id)->where('qualification_id', $qualifications[0]["id"])
                        ->orderby('id', 'asc')->withTrashed()->first();

                        if($existAssessors_ != null) {
                            if($existAssessors_->assessor_id != (int)$assessors[0]['id']) {

                                $isExist_ = UserAssessor::where('user_id', $user->id)->where('qualification_id', $qualifications[0]["id"])
                                ->where('assessor_id', (int)$assessors[0]['id'])->exists();

                                DB::table('user_assessors')->where('user_id', $user->id)->where('qualification_id', $qualifications[0]["id"])->delete();

                                // $assessors = json_decode($request->assessors, true);
            
                                foreach ($assessors as $assessor) {
                                    $assessor_record = [
                                        'user_id' =>  $user->id,
                                        'assessor_id' => $assessor['id'],
                                        'status' => 'active',
                                        'created_by' => Auth::id(),
                                        'updated_by' => Auth::id(),
                                        'qualification_id' => $qualifications[0]["id"]
                                    ];
            
                                    $response_ = UserAssessor::create($assessor_record);
                                    if($isExist_ == true) {
                                        UserAssessor::where('id', $response_->id)->delete();
                                    }
                                }
                            }
                        }                        
                    }
    
                    if ($request->iqas != null) {
                        $iqas = json_decode($request->iqas, true);
                        
                        $existIQAs_ = UserIqa::where('user_id', $user->id)->where('qualification_id', $qualifications[0]["id"])
                        ->orderby('id', 'asc')->withTrashed()->first();

                        if($existIQAs_ != null) {
                            if($existIQAs_->iqa_id != (int)$iqas[0]['id']) {

                                $isExist_iqa = UserIqa::where('user_id', $user->id)->where('qualification_id', $qualifications[0]["id"])
                                ->where('iqa_id', (int)$iqas[0]['id'])->exists();

                                DB::table('user_iqas')->where('user_id', $user->id)->where('qualification_id', $qualifications[0]["id"])->delete();
                            
                                foreach ($iqas as $iqa) {
                                    $iqa_record = [
                                        'user_id' =>  $user->id,
                                        'iqa_id' => $iqa['id'],
                                        'status' => 'active',
                                        'created_by' => Auth::id(),
                                        'updated_by' => Auth::id(),
                                        'qualification_id' => $qualifications[0]["id"]
                                    ];
            
                                    $response_iqa = UserIqa::create($iqa_record);

                                    if($isExist_iqa == true) {
                                        UserIqa::where('id', $response_iqa->id)->delete();
                                    }
                                }
                            }
                        }
                    }
                }                

                if ($request->references != null) {
                    UserReference::where('user_id', $user->id)->delete();
                    $references = json_decode($request->references, true);

                    foreach ($references as $reference) {
                        $reference_record = [
                            'user_id' =>  $user ? $user->id : 0,
                            'reference_no' => $reference['id'],
                            'status' => 'active',
                            'created_by' => Auth::id(),
                            'updated_by' => Auth::id(),
                        ];

                        UserReference::create($reference_record);
                    }
                }

                if ($request->learners != null) {
                    UserLearner::where('user_id', $user->id)->delete();
                    $learners = json_decode($request->learners, true);

                    foreach ($learners as $learner) {
                        $learner_record = [
                            'user_id' =>  $user ? $user->id : 0,
                            'learner_id' => $learner['id'],
                            'status' => 'active',
                            'created_by' => Auth::id(),
                            'updated_by' => Auth::id(),
                        ];

                        UserLearner::create($learner_record);
                    }
                }

                return response()->json([
                    'message' => 'Update successfully.',
                ], 200);
            } catch (\Exception $e) {

                if ($request->role_id == 3 && $deleteLearnerUserQuali_ && count($oldUserQualificationData) > 0 && count($new_user_qualification_lear) > 0) {
                    DB::table('user_qualifications')->whereIn('id', $new_user_qualification_lear)->delete();

                    $revert_UserQualification = [
                        'user_id' => $oldUserQualificationData[0]["user_id"],
                        'qualification_id' => $oldUserQualificationData[0]["qualification_id"],
                        'status' => $oldUserQualificationData[0]["status"],
                        'created_by' => $oldUserQualificationData[0]["created_by"],
                        'updated_by' => $oldUserQualificationData[0]["updated_by"],
                        'ref_number' => $oldUserQualificationData[0]["ref_number"],
                        'first_name' => $oldUserQualificationData[0]["first_name"],
                        'middle_name' => $oldUserQualificationData[0]["middle_name"],
                        'sur_name' => $oldUserQualificationData[0]["sur_name"],
                        'learner_number' => $oldUserQualificationData[0]["learner_number"],
                        'date_of_registration' => $oldUserQualificationData[0]["date_of_registration"],
                        'cohort_batch_no' => $oldUserQualificationData[0]["cohort_batch_no"],
                        'contact' => $oldUserQualificationData[0]["contact"],
                        'date_of_birth' => $oldUserQualificationData[0]["date_of_birth"],
                        'disability' => $oldUserQualificationData[0]["disability"],
                        'location' => $oldUserQualificationData[0]["location"],
                        'country' => $oldUserQualificationData[0]["country"],
                        'city' => $oldUserQualificationData[0]["city"],
                        'lat' => $oldUserQualificationData[0]["lat"],
                        'lon' => $oldUserQualificationData[0]["lon"],
                    ];

                    $revert_UserQualification_success = UserQualification::create($revert_UserQualification);                        
                }

                if (($request->role_id == 4 || $request->role_id == 5) && $deleteAssessorUserQuali_ && count($oldUserQualificationData) > 0 && count($new_user_qualification_Assess) > 0) {
                    DB::table('user_qualifications')->whereIn('id', $new_user_qualification_Assess)->delete();

                    foreach($oldUserQualificationData as $qualification_) {
                        $revert_UserQualification = [
                            'user_id' => $qualification_["user_id"],
                            'qualification_id' => $qualification_["qualification_id"],
                            'status' => $qualification_["status"],
                            'created_by' => $qualification_["created_by"],
                            'updated_by' => $qualification_["updated_by"],
                            'first_name' => $qualification_["first_name"],
                            'middle_name' => $qualification_["middle_name"],
                            'sur_name' => $qualification_["sur_name"],
                            'contact' => $qualification_["contact"],
                        ];
    
                        $revert_UserQualification_success = UserQualification::create($revert_UserQualification);  
                    }
                    
                }

                return response()->json([
                    'message' => 'Edit failed',
                    'error' => $e->getMessage(),
                ], 500);
            }
        } else {
            $new_user_id = null;
            $new_user_qualification = [];
            $new_user_ass = [];
            $new_user_iqa = [];
            $new_user_references = [];
            $new_user_learners = [];
            $user_role_new = null;

            $qualifications = $request->qualifications ? json_decode($request->qualifications, true) : [];

            $existingUser = User::where('email', $request->email)->pluck('id');

            if (count($existingUser) > 0) {
                if ($request->role_id != 3) {
                    return response()->json([
                        'message' => 'Validation errors',
                        'error' => 'This email already in use!'
                    ], 422);
                } else {
                    $existingUserAnotherRole = User::where('email', $request->email)->first();

                    if ($existingUserAnotherRole->role_id != 3) {
                        return response()->json([
                            'message' => 'Validation errors',
                            'error' => 'This email are already registered in another role!'
                        ], 422);
                    }
                    //this case is remaining 
                    else if ($existingUserAnotherRole->created_by != Auth::id()) {
                        return response()->json([
                            'message' => 'Validation errors',
                            'error' => 'This email already in use!'
                        ], 422);
                    }
                }
            }

            if (count($existingUser) > 0) {
                $existingQualifications = UserQualification::whereIn('user_id', $existingUser)->whereIn('created_by', Helper::getAdmin_ids(Auth::id()))
                    ->pluck('qualification_id')
                    ->toArray();

                $newQualifications = array_column($qualifications, 'id');

                if (array_intersect($newQualifications, $existingQualifications)) {
                    return response()->json([
                        'message' => 'Validation errors',
                        'error' => 'You are already registered with this email and qualifications'
                    ], 422);
                }
            }

            try {
                $password = str()->random(8);
                $check_record = User::where('email', $request->email)->first();
                if ($check_record == null) {
                    $userData = [
                        'email' => $request->email ?? null,
                        'role_id' => $request->role_id ?? null,
                        'first_name' => $request->first_name ?? null,
                        'middle_name' => $request->middle_name ?? null,
                        'sur_name' => $request->sur_name ?? null,
                        'contact' => $request->contact ?? null,
                        'email_verified_at' => Carbon::now(),
                        'status' => 'active',
                        'password' => Hash::make($password),
                        'customer_id' => Auth::user()->customer_id,
                        'created_by' =>  Auth::id(),
                        'updated_by' => Auth::id(),
                        'code' =>  Helper::getLastcode(),
                    ];

                    $user =  User::create($userData);
                    $new_user_id = $user->id;

                    if ((int)$request->role_id > 1) {
                        $user_role = [
                            'user_id' => $user->id,
                            'role_id' => $request->role_id,
                        ];

                        $create_user_role = UserRole::create($user_role);
                        $user_role_new = $create_user_role->id;
                    }
                } else {
                    $user =  $check_record;
                }

                $emailQualification = null;
                if ((int)$request->role_id != 6 && $request->qualifications != null) {
                    $qualifications = json_decode($request->qualifications, true);

                    foreach ($qualifications as $qualification) {
                        $qualification_record = [
                            'user_id' => $user ? $user->id : 0,
                            'qualification_id' => $qualification['id'],
                            'sampling_ratio' => $request->sampling_ratio ?? ($request->role_id == 4 ? 100 : 0),
                            'status' => 'active',
                            'created_by' => Auth::id(),
                            'updated_by' => Auth::id(),
                        ];

                        $user_qualification = UserQualification::create($qualification_record);
                        $user_qualification->ref_number = $request->ref_number ?? null;
                        $user_qualification->contact = $request->contact ?? null;
                        $user_qualification->date_of_birth = $request->date_of_birth ?? null;
                        $user_qualification->cohort_batch_no = $request->cohort_batch_no ?? null;
                        $user_qualification->date_of_registration = $request->date_of_registration ?? null;
                        $user_qualification->sampling_ratio = $request->sampling_ratio ?? null;
                        $user_qualification->view_only_id = $request->view_only_id ?? null;
                        $user_qualification->learner_number = $request->learner_number ?? null;
                        $user_qualification->location = $request->location ?? null;
                        $user_qualification->country = $request->country ?? null;
                        $user_qualification->city = $request->city ?? null;
                        $user_qualification->lat = $request->lat ?? null;
                        $user_qualification->lon = $request->lon ?? null;
                        $user_qualification->expiry_date = $request->expiry_date ?? null;
                        $user_qualification->first_name = $request->first_name ?? null;
                        $user_qualification->middle_name = $request->middle_name ?? null;
                        $user_qualification->sur_name = $request->sur_name ?? null;
                        $user_qualification->disability = ($request->role_id == 3 ? ($request->disability == "yes" ? true : false) : false);
                        $user_qualification->save();

                        $new_user_qualification[] = $user_qualification->id;

                        $qualificationName = Qualification::where('id', $qualification['id'])->first();
                        if($qualificationName != null) {
                            $emailQualification .= ($emailQualification != null ? ', ' : '') . $qualificationName->sub_title;
                        }
                    }
                }

                if ($request->assessors != null) {
                    $assessors = json_decode($request->assessors, true);
                    $assessor_qualifications = json_decode($request->qualifications, true);

                    $qual_id = 0;
                    foreach ($assessor_qualifications as $curr_qualification) {
                        $qual_id = $curr_qualification['id'];
                    }

                    foreach ($assessors as $assessor) {
                        $assessor_record = [
                            'user_id' =>  $user ? $user->id : 0,
                            'assessor_id' => $assessor['id'],
                            'qualification_id' => $qual_id,
                            'status' => 'active',
                            'created_by' => Auth::id(),
                            'updated_by' => Auth::id(),
                        ];

                        $user_ass =  UserAssessor::create($assessor_record);

                        $new_user_ass[] = $user_ass->id;
                    }
                }

                if ($request->iqas != null) {
                    $iqas = json_decode($request->iqas, true);
                    $iqa_qualifications = json_decode($request->qualifications, true);

                    $qual_id = 0;
                    foreach ($iqa_qualifications as $curr_qualification) {
                        $qual_id = $curr_qualification['id'];
                    }

                    foreach ($iqas as $iqa) {
                        $iqa_record = [
                            'user_id' =>  $user ? $user->id : 0,
                            'iqa_id' => $iqa['id'],
                            'qualification_id' => $qual_id,
                            'status' => 'active',
                            'created_by' => Auth::id(),
                            'updated_by' => Auth::id(),
                        ];

                        $user_iqa =  UserIqa::create($iqa_record);

                        $new_user_iqa[] = $user_iqa->id;
                    }
                }

                if ((int)$request->role_id != 6 && $request->references != null) {
                    $references = json_decode($request->references, true);

                    foreach ($references as $reference) {

                        $refUser = UserQualification::where('ref_number', $reference)->whereIn('created_by', Helper::getAdmin_ids(Auth::id()))->first();

                        $reference_record = [
                            'user_id' =>  $user ? $user->id : 0,
                            'reference_no' => ($refUser != null ? $refUser->user_id : 0),
                            'status' => 'active',
                            'created_by' => Auth::id(),
                            'updated_by' => Auth::id(),
                        ];

                        $user_ref =  UserReference::create($reference_record);

                        $new_user_references[] = $user_ref->id;
                    }
                }

                if ((int)$request->role_id != 6 && $request->learners != null) {
                    $learners = json_decode($request->learners, true);

                    foreach ($learners as $learner) {
                        $learner_record = [
                            'user_id' =>  $user ? $user->id : 0,
                            'learner_id' => $learner['id'],
                            'status' => 'active',
                            'created_by' => Auth::id(),
                            'updated_by' => Auth::id(),
                        ];

                        $user_learner = UserLearner::create($learner_record);

                        $new_user_learners[] = $user_learner->id;
                    }
                }


                if ($new_user_id != null) {
                    
                    $InstituteDetail = User::where('id', Auth::id())->first();
                    $InstituteName = null;
                    if ($InstituteDetail->first_name != null) {
                        $InstituteName .= $InstituteDetail->first_name;
                    }
            
                    if ($InstituteDetail->middle_name != null) {
                        $InstituteName .= ($InstituteName != null ? ' ' : '') . $InstituteDetail->middle_name;
                    }
            
                    if ($InstituteDetail->sur_name != null) {
                        $InstituteName .= ($InstituteName != null ? ' ' : '') . $InstituteDetail->sur_name;
                    }            

                    $credentials = [
                        'email' => $request->email,
                        'password' => $password,
                        'role' => $request->role_id,
                        'institute' => $InstituteName,
                        'qualification' => $emailQualification,
                    ];
                    
                    Helper::createUserCredentials($credentials);                    
                }

                return response()->json([
                    'message' => 'Created successfully.',
                ], 201);
            } catch (\Exception $e) {
                if ($new_user_id != null) {
                    DB::table('users')->where('id', $new_user_id)->delete();
                    DB::table('user_roles')->where('id', $user_role_new)->delete();
                }

                if (count($new_user_qualification) > 0) {
                    DB::table('user_qualifications')->whereIn('id', $new_user_qualification)->delete();
                }

                if (count($new_user_ass) > 0) {
                    DB::table('user_assessors')->whereIn('id', $new_user_ass)->delete();
                }

                if (count($new_user_iqa) > 0) {
                    DB::table('user_iqas')->whereIn('id', $new_user_iqa)->delete();
                }

                if (count($new_user_references) > 0) {
                    DB::table('user_references')->whereIn('id', $new_user_references)->delete();
                }

                if (count($new_user_learners) > 0) {
                    DB::table('user_learners')->whereIn('id', $new_user_learners)->delete();
                }

                return response()->json([
                    'message' => 'Creation failed',
                    'error' => $e->getMessage(),
                    'new_user_id' => $new_user_id,
                    'new_user_qualification' => $new_user_qualification,
                    'new_user_ass' => $new_user_ass,
                    'new_user_iqa' => $new_user_iqa,
                    'new_user_references' => $new_user_references,
                    'new_user_learners' => $new_user_learners,
                    'user_role_new' => $user_role_new,
                ], 500);
            }
        }
    }

    // public function get_learner_list(Request $request) {
    //     $validator = Validator::make($request->all(), [
    //         'company_admin_id' => 'required',
    //         'qualification_id' => 'required',
    //     ]);

    //     if ($validator->fails()) {
    //         $response_data = [
    //             'success' => false,
    //             'message' => 'Incomplete data provided!',
    //             'errors' => $validator->errors(),
    //         ];
    //         return response()->json($response_data);
    //     }

    //     $user = User::Join('user_qualifications', 'users.id', '=', 'user_qualifications.user_id')
    //             ->select('user_qualifications.*', 'user_qualifications.qualification_id');

    //     if ($request->has('search')) {
    //         $searchTerm = $request->input('search');

    //         $user->where(function ($query) use ($searchTerm) {
    //             $query->where('user_qualifications.first_name', 'like', "%$searchTerm%")
    //                 ->orWhere('user_qualifications.middle_name', 'like', "%$searchTerm%")
    //                 ->orWhere('user_qualifications.sur_name', 'like', "%$searchTerm%");
    //         });
    //     }

    //     $user->whereNull('user_qualifications.deleted_at')
    //     ->whereNull('users.deleted_at');

    //     $user->where('user_qualifications.qualification_id', $request->qualification_id)
    //     ->where('user_qualifications.created_by', $request->company_admin_id);

    //     $count = $user->count();
    //     $users = $user->paginate(10);

    //     if ($users->isEmpty()) {
    //         return response()->json(['error' => 'No user found.'], 404);
    //     }

    //     return response()->json([
    //         'message' => 'users',
    //         'data' => UserResource::collection($users),
    //         'count' => $count
    //     ], 200);
    // }

    public function get_users_V1(Request $request)
    {
        if ((int)$request->role_id == 3) {

            if($request->has('qualification_id')) {
                $user = User::Join('user_qualifications', 'users.id', '=', 'user_qualifications.user_id')
                ->where('user_qualifications.qualification_id', $request->qualification_id)
                ->select('users.*', 'user_qualifications.qualification_id');

                if($request->has('iqa_id')) {
                    $user_iqa = UserIqa::where('iqa_id', $request->iqa_id)->where('qualification_id', $request->qualification_id)->withTrashed()->pluck('user_id');
                    $user->whereIn('users.id', $user_iqa)->where('users.role_id', $request->role_id);                    
                }

                if($request->has('assessor_id'))
                {
                    $userAssessors = UserAssessor::where('qualification_id', $request->qualification_id)
                    ->where('assessor_id', $request->assessor_id)->withTrashed()->pluck('user_id');

                    $user->whereIn('users.id', $userAssessors)->where('users.role_id', $request->role_id);
                }

                if(Auth::user()->role_id == 4) {
                    $assessor_learners = UserAssessor::where('assessor_id', Auth::id())->where('qualification_id', $request->qualification_id)->pluck('user_id');
                    $user->whereIn('users.id', $assessor_learners)->where('users.role_id', $request->role_id); 
                } else if (Auth::user()->role_id == 5) {
                    $iqa_learners = UserIqa::where('iqa_id', Auth::id())->where('qualification_id', $request->qualification_id)->pluck('user_id');
                    $user->whereIn('users.id', $iqa_learners)->where('users.role_id', $request->role_id); 
                }

                $user->where('user_qualifications.qualification_id', $request->qualification_id);

            } else {
                $user = User::Join('user_qualifications', 'users.id', '=', 'user_qualifications.user_id');

                if($request->has('iqa_id'))
                {
                    $iqa_qualification = UserQualification::where('user_id', $request->iqa_id)->pluck('qualification_id');
                    $user_iqa = UserIqa::where('iqa_id', $request->iqa_id)->whereIn('qualification_id', $iqa_qualification)->pluck('user_id');
                    
                    $user->whereIn('users.id', $user_iqa);

                    $user = $user->select('users.*', 'user_qualifications.qualification_id');
                    $user->whereIn('user_qualifications.qualification_id', $iqa_qualification);

                } else {
                    $user = $user->select('users.*', 'user_qualifications.qualification_id');
                }

                
            }

            $user->whereNull('user_qualifications.deleted_at');
        } else {

            $user = User::select('users.*');
            //Filter IQA
            if($request->has('iqa_id') && (int)$request->role_id == 4)
            {
                $iqa_qualification = UserQualification::where('user_id', $request->iqa_id)->pluck('qualification_id');
                $user_iqa = UserIqa::where('iqa_id', $request->iqa_id)->whereIn('qualification_id', $iqa_qualification)->withTrashed()->pluck('user_id');

                $assessors_ = UserAssessor::whereIn('user_id', $user_iqa)->whereIn('qualification_id', $iqa_qualification)->withTrashed()->pluck('assessor_id');
                $user->whereIn('users.id', $assessors_);
            }
            //Filter QualificationID
            if($request->has('qualification_id')) {
                $userQualification = UserQualification::where('qualification_id', $request->qualification_id)->pluck('user_id');
                $user->whereIn('users.id', $userQualification);
            }
            //Filter AssessorID
            if($request->has('assessor_id'))
            {
                $assessors_ = UserAssessor::where('assessor_id', $request->assessor_id)->withTrashed()->pluck('user_id');
                $user->whereIn('users.id', $assessors_);
            }
        }

        $user->whereNull('users.deleted_at');

        if ($request->has('status')) {
            $user->where('users.status', $request->status);
        }

        if ($request->has('role_id')) {
            $user->where('users.role_id', $request->role_id);
        }

        if ($request->has('qualification_id') && (int)$request->role_id != 3) {

            $user_ids = UserQualification::where('qualification_id', $request->qualification_id)->pluck('user_id');
            $user->whereIn('users.id', $user_ids)->where('users.role_id', $request->role_id);            
        }

        if ($request->has('company_admin_id')) {
            $user->whereIn('users.created_by', Helper::getAdmin_ids($request->company_admin_id));
        }

        // filters start

        if ($request->qualification_ids) {
            $qualificationIdsArray = explode(',', $request->qualification_ids);
            $user_ids = UserQualification::whereIn('qualification_id', $qualificationIdsArray)->pluck('user_id');
            $user->whereIn('users.id', $user_ids)->where('users.role_id', $request->role_id);
        }

        if ($request->assessor_ids) {
            $assessorIdsArray = explode(',', $request->assessor_ids);
            $user_ids = UserAssessor::whereIn('assessor_id', $assessorIdsArray)->pluck('user_id');
            $user->whereIn('users.id', $user_ids)->where('users.role_id', $request->role_id);
        }

        if ($request->iqa_ids) {
            $iqaIdsArray = explode(',', $request->iqa_ids);
            $user_ids = UserIqa::whereIn('iqa_id', $iqaIdsArray)->pluck('user_id');
            $user->whereIn('users.id', $user_ids)->where('users.role_id', $request->role_id);
        }

        if ($request->eqa_ids) {
            $eqaIdsArray = explode(',', $request->eqa_ids);
            $user->whereIn('users.id', $eqaIdsArray)->where('users.role_id', $request->role_id);
        }

        if ($request->admin_ids) {
            $adminIdsArray = explode(',', $request->admin_ids);
            $user->whereIn('users.id', $adminIdsArray)->where('users.role_id', $request->role_id);
        }

        if ($request->batch_numbers) {
            $batch_numbers = explode(',', $request->batch_numbers);
            $user->whereIn('user_qualifications.cohort_batch_no', $batch_numbers);
        }

        if ($request->ref_numbers) {
            $ref_numbers = explode(',', $request->ref_numbers);
            $user->whereIn('user_qualifications.ref_number', $ref_numbers);
        }

        if ($request->name_ids) {
            $name_ids = explode(',', $request->name_ids);
            $user->whereIn('users.id', $name_ids)->where('users.role_id', $request->role_id);
        }

        if ($request->email_ids) {
            $email_ids = explode(',', $request->email_ids);
            $user->whereIn('users.id', $email_ids)->where('users.role_id', $request->role_id);
        }


        // filters end

        if ($request->has('search')) {
            $searchTerm = $request->input('search');

            if ((int)$request->role_id == 3) {
                $user->where(function ($query) use ($searchTerm) {
                    $query->where('user_qualifications.first_name', 'like', "%$searchTerm%")
                        ->orWhere('user_qualifications.middle_name', 'like', "%$searchTerm%")
                        ->orWhere('user_qualifications.sur_name', 'like', "%$searchTerm%")
                        ->orWhere('users.email', 'like', "%$searchTerm%");
                });
            } else {
                $user->where(function ($query) use ($searchTerm) {
                    $query->where('users.first_name', 'like', "%$searchTerm%")
                        ->orWhere('users.middle_name', 'like', "%$searchTerm%")
                        ->orWhere('users.sur_name', 'like', "%$searchTerm%")
                        ->orWhere('users.email', 'like', "%$searchTerm%");
                });
            }
        }

        $count = $user->count();
        $users = $user->paginate(10);

        if ($users->isEmpty()) {
            return response()->json(['error' => 'No user found.'], 404);
        }

        return response()->json([
            'message' => 'users',
            'data' => UserResource_V1::collection($users),
            'count' => $count
        ], 200);
    }

    public function get_users(Request $request)
    {
        //$user = User::query();

        if ((int)$request->role_id == 3) {

            if($request->has('qualification_id')) {
                $user = User::Join('user_qualifications', 'users.id', '=', 'user_qualifications.user_id')
                ->where('user_qualifications.qualification_id', $request->qualification_id)
                ->select('users.*', 'user_qualifications.qualification_id');

                if($request->has('iqa_id')) {
                    $user_iqa = UserIqa::where('iqa_id', $request->iqa_id)->where('qualification_id', $request->qualification_id)->withTrashed()->pluck('user_id');
                    //$user_iqa = UserIqa::where('iqa_id', $request->iqa_id)->whereIn('qualification_id', $iqa_qualification)->withTrashed()->pluck('user_id');
                    $user->whereIn('users.id', $user_iqa)->where('users.role_id', $request->role_id);                    
                }

                if($request->has('assessor_id'))
                {
                    $userAssessors = UserAssessor::where('qualification_id', $request->qualification_id)
                    ->where('assessor_id', $request->assessor_id)->withTrashed()->pluck('user_id');

                    $user->whereIn('users.id', $userAssessors)->where('users.role_id', $request->role_id);
                }

                if(Auth::user()->role_id == 4) {
                    $assessor_learners = UserAssessor::where('assessor_id', Auth::id())->where('qualification_id', $request->qualification_id)->pluck('user_id');
                    $user->whereIn('users.id', $assessor_learners)->where('users.role_id', $request->role_id); 
                } else if (Auth::user()->role_id == 5) {
                    $iqa_learners = UserIqa::where('iqa_id', Auth::id())->where('qualification_id', $request->qualification_id)->pluck('user_id');
                    $user->whereIn('users.id', $iqa_learners)->where('users.role_id', $request->role_id); 
                }

                $user->where('user_qualifications.qualification_id', $request->qualification_id);

            } else {
                $user = User::Join('user_qualifications', 'users.id', '=', 'user_qualifications.user_id');

                if($request->has('iqa_id'))
                {
                    $iqa_qualification = UserQualification::where('user_id', $request->iqa_id)->pluck('qualification_id');
                    $user_iqa = UserIqa::where('iqa_id', $request->iqa_id)->whereIn('qualification_id', $iqa_qualification)->pluck('user_id');
                    
                    $user->whereIn('users.id', $user_iqa);

                    $user = $user->select('users.*', 'user_qualifications.qualification_id');
                    $user->whereIn('user_qualifications.qualification_id', $iqa_qualification);

                } else {
                    $user = $user->select('users.*', 'user_qualifications.qualification_id');
                }

                
            }

            $user->whereNull('user_qualifications.deleted_at');
        } else {

            $user = User::select('users.*');
            //Filter IQA
            if($request->has('iqa_id') && (int)$request->role_id == 4)
            {
                $iqa_qualification = UserQualification::where('user_id', $request->iqa_id)->pluck('qualification_id');
                $user_iqa = UserIqa::where('iqa_id', $request->iqa_id)->whereIn('qualification_id', $iqa_qualification)->withTrashed()->pluck('user_id');

                $assessors_ = UserAssessor::whereIn('user_id', $user_iqa)->whereIn('qualification_id', $iqa_qualification)->withTrashed()->pluck('assessor_id');
                $user->whereIn('users.id', $assessors_);
            }
            //Filter QualificationID
            if($request->has('qualification_id')) {
                $userQualification = UserQualification::where('qualification_id', $request->qualification_id)->pluck('user_id');
                $user->whereIn('users.id', $userQualification);
            }
            //Filter AssessorID
            if($request->has('assessor_id'))
            {
                $assessors_ = UserAssessor::where('assessor_id', $request->assessor_id)->withTrashed()->pluck('user_id');
                $user->whereIn('users.id', $assessors_);
            }

            //$user = User::select('users.*');
        }

        $user->whereNull('users.deleted_at');

        if ($request->has('status')) {
            $user->where('users.status', $request->status);
        }

        if ($request->has('role_id')) {
            $user->where('users.role_id', $request->role_id);
        }

        // if ($request->has('country')) {
        //     $user->where('user_qualifications.country', $request->country);
        // }

        if ($request->has('qualification_id') && (int)$request->role_id != 3) {

            $user_ids = UserQualification::where('qualification_id', $request->qualification_id)->pluck('user_id');
            $user->whereIn('users.id', $user_ids)->where('users.role_id', $request->role_id);            
        }

        if ($request->has('company_admin_id')) {
            $user->whereIn('users.created_by', Helper::getAdmin_ids($request->company_admin_id));
        }

        // filters start

        if ($request->qualification_ids) {
            $qualificationIdsArray = explode(',', $request->qualification_ids);
            $user_ids = UserQualification::whereIn('qualification_id', $qualificationIdsArray)->pluck('user_id');
            $user->whereIn('users.id', $user_ids)->where('users.role_id', $request->role_id);
        }

        if ($request->assessor_ids) {
            $assessorIdsArray = explode(',', $request->assessor_ids);
            $user_ids = UserAssessor::whereIn('assessor_id', $assessorIdsArray)->pluck('user_id');
            $user->whereIn('users.id', $user_ids)->where('users.role_id', $request->role_id);
        }

        if ($request->iqa_ids) {
            $iqaIdsArray = explode(',', $request->iqa_ids);
            $user_ids = UserIqa::whereIn('iqa_id', $iqaIdsArray)->pluck('user_id');
            $user->whereIn('users.id', $user_ids)->where('users.role_id', $request->role_id);
        }

        if ($request->eqa_ids) {
            $eqaIdsArray = explode(',', $request->eqa_ids);
            $user->whereIn('users.id', $eqaIdsArray)->where('users.role_id', $request->role_id);
        }

        if ($request->admin_ids) {
            $adminIdsArray = explode(',', $request->admin_ids);
            $user->whereIn('users.id', $adminIdsArray)->where('users.role_id', $request->role_id);
        }

        if ($request->batch_numbers) {
            $batch_numbers = explode(',', $request->batch_numbers);
            $user->whereIn('user_qualifications.cohort_batch_no', $batch_numbers);
        }

        if ($request->ref_numbers) {
            $ref_numbers = explode(',', $request->ref_numbers);
            $user->whereIn('user_qualifications.ref_number', $ref_numbers);
        }

        if ($request->name_ids) {
            $name_ids = explode(',', $request->name_ids);
            $user->whereIn('users.id', $name_ids)->where('users.role_id', $request->role_id);
        }

        if ($request->email_ids) {
            $email_ids = explode(',', $request->email_ids);
            $user->whereIn('users.id', $email_ids)->where('users.role_id', $request->role_id);
        }


        // filters end

        if ($request->has('search')) {
            $searchTerm = $request->input('search');

            if ((int)$request->role_id == 3) {
                $user->where(function ($query) use ($searchTerm) {
                    $query->where('user_qualifications.first_name', 'like', "%$searchTerm%")
                        ->orWhere('user_qualifications.middle_name', 'like', "%$searchTerm%")
                        ->orWhere('user_qualifications.sur_name', 'like', "%$searchTerm%")
                        ->orWhere('users.email', 'like', "%$searchTerm%");
                });
            } else {
                $user->where(function ($query) use ($searchTerm) {
                    $query->where('users.first_name', 'like', "%$searchTerm%")
                        ->orWhere('users.middle_name', 'like', "%$searchTerm%")
                        ->orWhere('users.sur_name', 'like', "%$searchTerm%")
                        ->orWhere('users.email', 'like', "%$searchTerm%");
                });
            }
        }

        $count = $user->count();
        $users = $user->paginate(10);

        if ($users->isEmpty()) {
            return response()->json(['error' => 'No user found.'], 404);
        }

        return response()->json([
            'message' => 'users',
            'data' => UserResource::collection($users),
            'count' => $count
        ], 200);
    }

    public function get_users_name(Request $request)
    {
        $user = User::query();

        if ($request->has('search')) {
            $searchTerm = $request->input('search');
            $user->where('first_name', 'like', "%$searchTerm%")
                ->orWhere('middle_name', 'like', "%$searchTerm%")
                ->orWhere('sur_name', 'like', "%$searchTerm%")
                ->orWhere('email', 'like', "%$searchTerm%")
                ->orWhere('location', 'like', "%$searchTerm%");
        }

        if ($request->company_admin_id) {
            $user = $user->whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id));
        }

        if ((int)Auth::user()->role_id == 3) {
            $user_assessor = UserAssessor::where('user_id', Auth::id())->pluck('assessor_id');
            $user_assessor[] = $request->company_admin_id;

            $user = User::whereIn('id', $user_assessor);
        } else {
            $user = $user->whereNotIn('id', [Auth::id()]);
        }

        $users = $user->get();

        if ($users->isEmpty()) {
            return response()->json(['error' => 'No user found.'], 404);
        }

        return response()->json([
            'message' => 'users name',
            'data' => UserNameResource::collection($users),
        ], 200);
    }

    public function get_batch_no(Request $request)
    {
        $users = User::where('cohort_batch_no', '!=', null)->get();

        if ($users->isEmpty()) {
            return response()->json(['error' => 'No batch no found.'], 404);
        }

        $uniqueBatchNos = $users->pluck('cohort_batch_no')->unique();

        $batchNos = $uniqueBatchNos->map(function ($batchNo) {
            return ['cohort_batch_no' => $batchNo];
        });

        return response()->json([
            'message' => 'Batch no',
            'data' => $batchNos->values(),
        ], 200);
    }


    public function get_assigned_learners(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'user_id' => 'required',
            'role_id' => 'required',
        ]);

        if ($validator->fails()) {
            $response_data = [
                'success' => false,
                'message' => 'Incomplete data provided!',
                'errors' => $validator->errors(),
            ];
            return response()->json($response_data);
        }

        $user = null;

        switch ($request->role_id) {
            case 4:     //Assessors
                $user = UserAssessor::where('assessor_id', $request->user_id)
                    ->Join('users', 'users.id', '=', 'user_assessors.user_id')
                    ->select('users.*');

                break;
            case 5:     //IQA
                $user = UserIqa::where('iqa_id', $request->user_id)
                    ->Join('users', 'users.id', '=', 'user_iqas.user_id')
                    ->select('users.*');
                break;
            case 7:     //EQA
                $user = UserLearner::where('user_id', $request->user_id)
                    ->Join('users', 'users.id', '=', 'user_learners.learner_id')
                    ->select('users.*');
                break;
        }

        $count = $user->count();

        if ($request->has('page')) {
            $users = $user->paginate(20);
        } else {
            $users = $user->get();
        }

        if ($users->isEmpty()) {
            return response()->json(['error' => 'No learners found.'], 404);
        }

        return response()->json([
            'message' => 'Assigned Learners',
            'data' => UserResource_V1::collection($users),
            'count' => $count
        ], 200);
    }

    public function get_user_detail(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'user_id' => 'required',
            //'qualification_id' => 'required',
            'company_admin_id' => 'required',
        ]);

        if ($validator->fails()) {
            $response_data = [
                'success' => false,
                'message' => 'Incomplete data provided!',
                'errors' => $validator->errors(),
            ];
            return response()->json($response_data);
        }

        // $user = User::where('id', $request->user_id)->first();

        $userInfo = User::where('id', $request->user_id)->first();

        if ((int)$userInfo->role_id == 3) {
            $user = User::where('users.id', $request->user_id)
                ->whereIn('users.created_by', Helper::getAdmin_ids($request->company_admin_id))
                ->Join('user_qualifications', 'users.id', '=', 'user_qualifications.user_id')
                // ->where('user_qualifications.user_id', $request->user_Id)
                ->where('user_qualifications.qualification_id', $request->qualification_id)
                ->select('users.*', 'user_qualifications.qualification_id')->first();
        } else {
            $user = User::where('users.id', $request->user_id)
                ->whereIn('users.created_by', Helper::getAdmin_ids($request->company_admin_id))->first();
        }

        if ($user == null) {
            return response()->json(['error' => 'No user found.'], 404);
        }

        return response()->json([
            'message' => 'user detail',
            'data' => new UserResource($user)
        ], 200);
    }

    public function get_user_detail_V1(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'user_id' => 'required',
            //'qualification_id' => 'required',
            'company_admin_id' => 'required',
        ]);

        if ($validator->fails()) {
            $response_data = [
                'success' => false,
                'message' => 'Incomplete data provided!',
                'errors' => $validator->errors(),
            ];
            return response()->json($response_data);
        }

        // $user = User::where('id', $request->user_id)->first();

        $userInfo = User::where('id', $request->user_id)->first();

        if ((int)$userInfo->role_id == 3) {
            $user = User::where('users.id', $request->user_id)
                ->whereIn('users.created_by', Helper::getAdmin_ids($request->company_admin_id))
                ->Join('user_qualifications', 'users.id', '=', 'user_qualifications.user_id')
                // ->where('user_qualifications.user_id', $request->user_Id)
                ->where('user_qualifications.qualification_id', $request->qualification_id)
                ->select('users.*', 'user_qualifications.qualification_id')->first();
        } else {
            $user = User::where('users.id', $request->user_id)
                ->whereIn('users.created_by', Helper::getAdmin_ids($request->company_admin_id))->first();
        }

        if ($user == null) {
            return response()->json(['error' => 'No user found.'], 404);
        }

        return response()->json([
            'message' => 'user detail',
            'data' => new UserDetailResource_V1($user)
        ], 200);
    }

    public function get_user_roles(Request $request)
    {
        try {

            $roles_ = [1,2];

            if((int)Auth::user()->role_id == 6) {
                $roles_ = [1,2,6];
            }

            $data = Role::orderby('created_at', 'asc')->whereNotIn('id', $roles_)->get();

            if (count($data) > 0) {
                return response()->json([
                    'success' => true,
                    'message' => 'User Role List',
                    'data' => RoleResource::collection($data),
                ], 200);
            } else {
                return response()->json([
                    'success' => false,
                    'message' => 'Data Not Found.',
                ], 404);
            }
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function bulk_user_edit(Request $request)
    {
        $qualification_id = $request->qualification_id;
        $assessor_id = $request->assessor_id;
        $iqa_id = $request->iqa_id;
        $message = $request->message;
        $attachment_name = null;

        if ($request->hasfile('attachment')) {
            $extension = $request->file('attachment')->extension();
            $attachment = $request->file('attachment');
            $attachment_name = Str::random(20) . '.' . $extension;

            $path = 'bulk_update/' . $attachment_name;
            Helper::FileUpload($path, $attachment);
            // Storage::disk('local')->put(
            //     '/public/bulk_update/' . $attachment_name,
            //     File::get($attachment)
            // );
        }

        $errorMessage_ = null;

        if ($request->ids != null) {
            $ids = explode(',', $request->ids);

            foreach ($ids as $curr_id) {

                $email_data = [
                    'old_qualification' => '',
                    'new_qualification' => '',
                    'old_assessor' => '',
                    'new_assessor' => '',
                    'old_iqa' => '',
                    'new_iqa' => '',
                ];

                $oldQualificationId = null;
                $oldAssessorId = null;
                $oldIqaId = null;
                $newQualificationId = null;
                $newAssessorId = null;
                $newIqaId = null;


                $existingId = UserQualification::where('id', $curr_id)->first();
                $oldQualificationId_ = $existingId->qualification_id;
                $oldUserId_ = $existingId->user_id;


                if ($qualification_id) {

                    $info = UserQualification::where('user_id', $oldUserId_)->where('qualification_id', $qualification_id)->count();

                    if ($info <= 0) {
                        $old_qua = Qualification::where('id', $oldQualificationId_)->first();
                        $new_qua = Qualification::where('id', $qualification_id)->first();
                        if ($old_qua) {
                            $email_data['old_qualification'] = $old_qua->sub_title;
                        }
                        if ($new_qua) {
                            $email_data['new_qualification'] = $new_qua->sub_title;
                        }

                        $oldQualificationId = $oldQualificationId_;
                        $newQualificationId = $qualification_id;

                        // $log = [
                        //     'user_id' => $existingId->user_id,
                        //     'message' => $message,
                        //     'attachment' => $attachment_name,
                        //     'pre_qualification_id' => $existingId->qualification_id,
                        //     'new_qualification_id' => $qualification_id,
                        //     'created_by' => Auth::id(),
                        //     'updated_by' => Auth::id(),
                        // ];
                        // UpdateUserDetailLog::create($log);       

                        $existingId->qualification_id = $qualification_id;
                        $existingId->save();
                    }
                }

                if ($assessor_id) {
                    // Fetch old data
                    $old_data = UserAssessor::where('user_id', $oldUserId_)->where('qualification_id', $oldQualificationId_)->get();


                    foreach ($old_data as $data) {

                        $old_assessor = User::where('id', $data->assessor_id)->first();
                        $new_assessor = User::where('id', $assessor_id)->first();

                        if ($old_assessor) {
                            $email_data['old_assessor'] = $old_assessor->sur_name;
                        }
                        if ($new_assessor) {
                            $email_data['new_assessor'] = $new_assessor->sur_name;
                        }

                        $oldAssessorId = $data->assessor_id;
                        $newAssessorId = $assessor_id;


                        $currData = UserAssessor::where('id', $data->id)->first();

                        $currData->qualification_id = $qualification_id;
                        $currData->assessor_id = $assessor_id;
                        $currData->save();
                    }
                }

                if ($iqa_id) {

                    $old_data = UserIqa::where('user_id', $oldUserId_)->where('qualification_id', $oldQualificationId_)->get();

                    foreach ($old_data as $data) {

                        $old_iqa = User::where('id', $data->iqa_id)->first();
                        $new_iqa = User::where('id', $iqa_id)->first();

                        if ($old_iqa) {
                            $email_data['old_iqa'] = $old_iqa->sur_name;
                        }
                        if ($new_iqa) {
                            $email_data['new_iqa'] = $new_iqa->sur_name;
                        }

                        $oldIqaId = $data->iqa_id;
                        $newIqaId = $iqa_id;

                        $currData = UserIqa::where('id', $data->id)->first();

                        $currData->qualification_id = $qualification_id;
                        $currData->iqa_id = $iqa_id;
                        $currData->save();
                    }
                }

                $log = [
                    'user_id' => $existingId->user_id,
                    'message' => $message,
                    'attachment' => $attachment_name,
                    'pre_qualification_id' => $oldQualificationId,
                    'new_qualification_id' => $newQualificationId,
                    'pre_assessor_id' => $oldAssessorId,
                    'new_assessor_id' => $newAssessorId,
                    'pre_iqa_id' => $oldIqaId,
                    'new_iqa_id' => $newIqaId,
                    'created_by' => Auth::id(),
                    'updated_by' => Auth::id(),
                ];
                UpdateUserDetailLog::create($log);


                $user_data = User::where('id', $existingId->user_id);
                if ($user_data) {
                    Mail::to($user_data->email)->send(new BulkEditUserMail($email_data));
                }
            }
        }

        $user_data = User::where('role_id', 3)->get();

        if ($user_data->isEmpty()) {
            return response()->json(['error' => 'No user found.'], 404);
        }

        return response()->json([
            'message' => 'Bulk Edit',
            'data' => UserResource::collection($user_data),
        ], 200);
    }

    public function send_message(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'to' => 'required',
            'topic' => 'required',
            'message' => 'required',
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        try {

            $toIdsArray = explode(',', $request->to);
            //dd(count($toIdsArray));
            if (count($toIdsArray) > 0) {
                $user_ids = User::whereIn('id', $toIdsArray)->pluck('id');
            } else {
                $user_ids = User::where('id', $request->to)->pluck('id');
            }


            // $asp = str_replace('"', '', $request->to);
            // dd($asp);

            // $user_ids = User::where('id', (int)$request->to)->pluck('id');

            // $user->whereIn('users.id', $user_ids)->where('users.role_id', $request->role_id);

            if (count($user_ids) > 0) {
                foreach ($user_ids as $id_) {
                    $communication = [
                        'to_id' =>  $id_,
                        'topic' => $request->topic,
                        'message' => $request->message,
                        'status' => 'active',
                        'created_by' => Auth::id(),
                        'updated_by' => Auth::id(),
                    ];

                    Communication::create($communication);
                }
            } else {
                return response()->json([
                    'message' => 'User not found!',
                ], 422);
            }


            return response()->json([
                'message' => 'Message send successfully.',
            ], 201);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Creation failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_message(Request $request)
    {
        if((int)Auth::user()->role_id == 2 || (int)Auth::user()->role_id == 6) {
            $message_list = Communication::whereIn('to_id', Helper::getAdmin_ids(Auth::id()))->orWhereIn('created_by', Helper::getAdmin_ids(Auth::id()))
            ->orderby('created_at', 'desc');
        } else {
            $message_list = Communication::where('to_id', Auth::id())->orWhere('created_by', Auth::id())
            ->orderby('created_at', 'desc');
        }
        

        $count = $message_list->count();

        if ($request->has('page')) {
            $communications = $message_list->paginate(20);
        } else {
            $communications = $message_list->get();
        }

        if ($communications->isEmpty()) {
            return response()->json(['error' => 'No message found.'], 201);
        }

        return response()->json([
            'message' => 'Message list',
            'data' => CommunicationResource::collection($communications),
            'count' => $count
        ], 200);
    }

    public function mark_seen(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'id' => 'required',
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        try {
            Communication::where('id', $request->id)->update(['is_seen' => 1]);

            return response()->json([
                'message' => 'Mark seen successfully.',
            ], 201);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function download_portfolio(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'company_admin_id' => 'required',
            'learner_id' => 'required',
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        try {
            // $directoryPath = storage_path('app/public/' . $request->company_admin_id . '/submissions/' . $request->learner_id);
            $directoryPath = Helper::GetFiles() . "submissions" . $request->learner_id;


            if (!File::exists($directoryPath)) {
                abort(404, 'Directory not found.');
            }

            $zipFileName = 'portfolio_' . $request->learner_id . '.zip';
            // $zipFilePath = storage_path('app/public/' . $zipFileName);
            $zipFilePath = Helper::GetFiles() . $zipFileName;


            $zip = new \ZipArchive();

            if ($zip->open($zipFilePath, \ZipArchive::CREATE | \ZipArchive::OVERWRITE) === TRUE) {
                $files = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($directoryPath));

                foreach ($files as $file) {
                    if (!$file->isDir()) {
                        $filePath = $file->getRealPath();
                        $relativePath = substr($filePath, strlen($directoryPath) + 1);
                        $zip->addFile($filePath, $relativePath);
                    }
                }

                $zip->close();

                return response()->download($zipFilePath)->deleteFileAfterSend(true);
            } else {
                return response()->json([
                    'message' => 'Could not create zip file',
                ], 500);
            }
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Download failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function user_import(Request $request)
    {
        // Validate the file input
        $validator = Validator::make($request->all(), [
            'file' => 'required|file|mimes:xlsx,csv', // Ensure the file is of type xlsx or csv
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        try {
            $fileName = $request->file('file')->getClientOriginalName();
            $import = new LearnerImport($fileName);
            Excel::import($import, $request->file('file'));

            // Check if there were any errors
            if (Storage::disk('s3')->exists($import->errorFileName)) {
                // chmod(storage_path('app/' . $import->errorFileName), 0775);

                //$errorFileUrl = URL::to('/') . Storage::disk('local')->url($import->errorFileName);
                $errorFileUrl = Storage::disk('s3')->url($import->errorFileName);

                return response()->json([
                    'message' => 'Import completed with some errors',
                    'error_file_url' => $errorFileUrl,
                ], 200);
            }

            return response()->json([
                'message' => 'Import successfully completed',
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Import failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_summary_user_qualification(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'user_id' => 'required',
            'qualification_id' => 'required',
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        $qualification_ac_count = QualificationAc::where('qualification_id', $request->qualification_id)->withTrashed()->count();
        $user_submission_count = QualificationSubmission::where('qualification_id', $request->qualification_id)
            ->where('created_by', $request->user_id)
            ->where('status', 'Accept')
            ->count();

        if ($qualification_ac_count == 0) {
            return response()->json([
                'complete_percentage' => 0,
                'incomplete_percentage' => 100
            ], 200);
        }

        $complete_percentage = ($user_submission_count / $qualification_ac_count) * 100;
        $incomplete_percentage = 100 - $complete_percentage;

        return response()->json([
            'complete_percentage' => (float)number_format($complete_percentage, 2, '.', ','),
            'incomplete_percentage' => (float)number_format($incomplete_percentage, 2, '.', ',')
        ], 200);
    }

    public function get_qualification_bars(Request $request)
    {
        $data = [
            ["date" => "01 Jan 2023", "from" => 10, "to" => 20],
            ["date" => "01 Jan 2024", "from" => 15, "to" => 25],
            ["date" => "01 Jan 2025", "from" => 20, "to" => 30]
        ];

        $dateArray = [];
        $rangeArray = [];

        foreach ($data as $item) {
            if (isset($item['date'])) {
                $dateArray[] = ['date' => $item['date']];
            }

            if (isset($item['from']) && isset($item['to'])) {
                $rangeArray[] = ['from' => $item['from'], 'to' => $item['to']];
            }
        }

        return response()->json([
            'dates' => ["01 Jan 2023", "01 Jan 2023", "01 Jan 2023", "01 Jan 2023"],
            'ranges' => $rangeArray,
            'data' => [10, 20, 30, 14]
        ], 200);
    }

    public function change_sampling_ratio(Request $request)
    {

        $validator = Validator::make($request->all(), [
            'user_id' => 'required',
            'qualification_id' => 'required',
            'company_admin_id' => 'required',
            'value' => 'required',
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        try {
            $assessor = UserQualification::where('user_id', $request->user_id)
                ->where('qualification_id', $request->qualification_id)
                ->whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id))
                ->first();

            if ($assessor == null) {
                return response()->json([
                    'message' => 'Assessor not found!'
                ], 422);
            } else {

                $assessor->sampling_ratio = $request->value;
                $assessor->save();

                return response()->json([
                    'message' => 'Sampling ratio update successfully!',
                ], 200);
            }
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function create_customer(Request $request)
    {
        if ($request->id) {
            $validator = Validator::make($request->all(), [
                'name' => 'required|max:255',
                'price' => 'required',
                'payment_terms' => 'required',
                'customer_address' => 'required|max:255',
                'billing_address' => 'required|max:255',
                // 'vat' => 'required',
            ]);
        } else {
            $validator = Validator::make($request->all(), [
                'name' => 'required|max:255',
                // 'email' => 'required|email|max:255|unique:users,email',
                'email' => [
                    'required',
                    'email',
                    'max:255',
                    function ($attribute, $value, $fail) {
                        if (
                            DB::table('users')->where('email', $value)->exists() ||
                            DB::table('customers')->where('email', $value)->exists()
                        ) {
                            $fail('The ' . $attribute . ' has already been taken.');
                        }
                    },
                ],
                'price' => 'required',
                'payment_terms' => 'required',
                'customer_address' => 'required|max:255',
                'billing_address' => 'required|max:255',
                // 'vat' => 'required',
            ]);
        }


        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        if ($request->id) {
            try {
                
                if($request->email != null) {
                    $emailExist_ = Customer::where('email', $request->email)->where('id', '!=', $request->id)->first();
                    if($emailExist_ != null) {
                        return response()->json([
                            'message' => 'Validation errors',
                            'error' => "Email already exist!"
                        ], 422);
                    }
                }                

                $customer = Customer::where('id', $request->id)->first();
                $customer->name = $request->name ?? null;
                $customer->email = $request->email ?? $customer->email;
                $customer->price = $request->price ?? null;
                $customer->payment_terms = $request->payment_terms ?? null;
                $customer->customer_address = $request->customer_address ?? null;
                $customer->billing_address = $request->billing_address ?? null;
                $customer->vat = $request->vat ?? false;
                $customer->save();

                $user_ = User::where('customer_id', $request->id)->where('role_id', '2')->first();

                if($user_ != null) {
                    $user_->sur_name = $request->name ?? $user_->sur_name;
                    $user_->email = $request->email ?? $user_->email;
                    $user_->save();
                }

                return response()->json([
                    'message' => 'Update successfully.',
                ], 200);
            } catch (\Exception $e) {
                return response()->json([
                    'message' => 'Edit failed',
                    'error' => $e->getMessage(),
                ], 500);
            }
        } else {
            try {
                $customerData = [
                    'name' => $request->name ?? null,
                    'email' => $request->email ?? null,
                    'price' => $request->price ?? null,
                    'payment_terms' => $request->payment_terms ?? null,
                    'customer_address' => $request->customer_address ?? null,
                    'billing_address' => $request->billing_address ?? null,
                    'vat' => $request->vat ?? false,
                ];

                $customer = Customer::create($customerData);

                $customer->customer_id = date('m/Y') . '/' . $customer->id;
                $customer->save();

                $password = str()->random(8);

                $userData = [
                    'role_id' => 2,
                    'sur_name' => $request->name ?? null,
                    'email' => $request->email ?? null,
                    'password' => Hash::make($password),
                    'email_verified_at' => Carbon::now(),
                    'customer_id' => $customer->id,
                    'created_by' => Auth::id(),
                    'updated_by' => Auth::id(),
                ];

                $user_ = User::create($userData);

                if($user_ != null) {
                    $user_role = [
                        'user_id' => $user_->id,
                        'role_id' => 2,
                    ];

                    $create_user_role = UserRole::create($user_role);
                }

                // if (env('IsEmail') == true) {
                //     $credentials = [
                //         'email' => $request->email,
                //         'password' => $password
                //     ];

                //     Helper::createUserCredentials($credentials);
                // }
                

                    $credentials = [
                        'email' => $request->email,
                        'password' => $password,
                        'role' => 2,
                        'institute' => "AssessEEZ",
                        'qualification' => "",
                    ];
                    
                    Helper::createUserCredentials($credentials);                    
                



                return response()->json([
                    'message' => 'Created successfully.',
                ], 200);
            } catch (\Exception $e) {
                return response()->json([
                    'message' => 'Creation failed',
                    'error' => $e->getMessage(),
                ], 500);
            }
        }
    }

    public function get_customer(Request $request)
    {
        try {
            $cusromer = Customer::query();

            if ($request->has('status')) {
                $cusromer = $cusromer->where('status', $request->status);
            }

            if ($request->has('id')) {
                $cusromer = $cusromer->where('id', $request->id);
            }

            if ($request->has('search')) {
                $searchTerm = $request->input('search');
                $cusromer->where('name', 'like', "%$searchTerm%")
                    ->orWhere('email', 'like', "%$searchTerm%")
                    ->orWhere('customer_id', 'like', "%$searchTerm%")
                    ->orWhere('price', 'like', "%$searchTerm%")
                    ->orWhere('customer_address', 'like', "%$searchTerm%")
                    ->orWhere('billing_address', 'like', "%$searchTerm%")
                    ->orWhere('vat', 'like', "%$searchTerm%");
            }

            $count = $cusromer->count();
            $cusromers = $cusromer->orderBy('created_at', 'desc')->paginate(10);

            if ($cusromers->isEmpty()) {
                return response()->json(['error' => 'No customer found.'], 404);
            }

            return response()->json([
                'message' => 'Customer',
                'data' => CustomerResource::collection($cusromers),
                'count' => $count
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function action_customer_status(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'id' => 'required',
                'status' => 'required',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            $customer = Customer::where('id', $request->id)->first();

            if ($customer != null) {                
                $customer->status = $request->status;
                $customer->save();

                $user = User::where('customer_id', $customer->id)->where('role_id', '2')->first();
                if($user != null) {
                    $user->status = $request->status;
                    $user->save();
                }
            }

            return response()->json([
                'message' => 'Customer ' . $request->status . ' Successfully',
                'data' => new CustomerResource($customer)
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Failed to change',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function save_assessor_documents(Request $request)
    {
        try {

            $validator = Validator::make($request->all(), [
                'user_id' => 'required',
                'qualification_id' => 'required',
                'title' => 'required', 
            //     'file' => 'max:102400',
            // ], [
            //     'file.max' => 'The file size must not exceed 100 MB.',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            $attachement_ = [
                'user_id' =>  $request->user_id,
                'title' => $request->title,
                'qualification_id' =>  $request->qualification_id,
                // 'attachment' => $url,
                'status' => 'active',
                'created_by' => Auth::id(),
                'updated_by' => Auth::id(),
            ];

            $attachement_response = AssessorDocument::create($attachement_);

            if ($request->hasFile('file')) {

                $basic_url = 'assessor_documents/' . Auth::id();

                foreach ($request->file as $curr_file) {
                    $extension = $curr_file->extension();
                    $attachement = $curr_file;
                    $url = Str::random(20) . '.' . $extension;

                    $path = ($basic_url . "/" . $url);
                    Helper::FileUpload($path, $attachement);                    

                    $assessor_attachement = [
                        'assessor_document_id' =>  $attachement_response->id,
                        'attachement' => $url,
                        'created_by' => Auth::id(),
                        'updated_by' => Auth::id(),
                    ];

                    $assessor_attachement_response = AssessorDocumentAttachement::create($assessor_attachement);
                }
            } else {
                return response()->json([
                    'message' => 'something went wrong!'
                ], 422);
            }

            return response()->json([
                'message' => 'Document successfully.',
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_assessor_documents(Request $request)
    {
        $data = AssessorDocument::query();

        if ($request->user_id) {
            $data = $data->where('user_id', $request->user_id);
        }

        if ($request->qualification_id) {
            $data = $data->where('qualification_id', $request->qualification_id);
        }

        $data = $data->get();

        return response()->json([
            'message' => 'Assessor Documents',
            'data' => AssessorDocumenResource_V1::collection($data)
        ], 200);
    }

    public function get_analytics(Request $request)
    {
        try {
            // $data = UserQualification::query();
            $data = UserQualification::leftJoin('users', function($join) {
                $join->on('user_qualifications.user_id', '=', 'users.id');
              })->where('users.role_id', 3)
              ->select('user_qualifications.*');

            if ($request->company_ids) {
                $company_ids = explode(',', $request->company_ids);

                $userList = User::where('role_id', '2')->whereIn('customer_id', $company_ids)->pluck('id');
                $data = $data->whereIn('user_qualifications.created_by', $userList);
            }

            if ($request->date_from && !$request->date_to) {
                $data = $data->where('user_qualifications.created_at', '>=', $request->date_from);
            } elseif (!$request->date_from && $request->date_to) {
                $data = $data->where('user_qualifications.created_at', '<=', $request->date_to);
            } elseif ($request->date_from && $request->date_to) {
                $data = $data->whereBetween('user_qualifications.created_at', [$request->date_from, $request->date_to]);
            }

            if ($request->status) {
                $data = $data->where('user_qualifications.status', $request->status);
            }

            $data = $data->count();

            return response()->json([
                'message' => 'Analytics',
                'data' => $data,
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_number_format(Request $request) {

       
       $val_w_format =  str_pad($request->number, 5, '0', STR_PAD_LEFT);

       dd($val_w_format);
    
        return $val_w_format;
    }
}
