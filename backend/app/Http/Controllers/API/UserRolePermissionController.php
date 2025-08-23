<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Http\Helpers\Helper;
use App\Http\Resources\PermissionPermissionTypeResource;
use App\Http\Resources\PermissionResource;
use App\Http\Resources\PermissionTypeResource;
use App\Http\Resources\RolePermissionResource;
use App\Http\Resources\RoleResource;
use App\Http\Resources\UserResource;
use App\Http\Resources\UserRoleResource;
use App\Models\Permission;
use App\Models\PermissionPermissionType;
use App\Models\PermissionType;
use App\Models\Role;
use App\Models\RolePermission;
use App\Models\User;
use App\Models\UserRole;
use Carbon\Carbon;
use Exception;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Validator;
use Illuminate\Support\Str;

class UserRolePermissionController extends Controller
{
    public function roles(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'role_name' => 'required',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            if ($request->id != null) {
                $request_data = Role::where('id', $request->id)->first();

                if (!$request_data) {
                    return response()->json([
                        'message' => 'Role not found',
                    ], 404);
                }

                $input = $request->all();
                $request_data->role_name = $input['role_name'];
                $request_data->status = 'active';
                $request_data->updated_at = Carbon::now();
                $request_data->save();

                $resource = new RoleResource($request_data);

                return response()->json([
                    'message' => 'Role edited successfully',
                    'data' => $resource,
                ], 200);
            } else {
                $input = $request->all();
                $input['role_name'] = $request['role_name'];
                $input['status'] = 'active';

                $request_data = Role::create($input);
                $resource = new RoleResource($request_data);

                return response()->json([
                    'message' => 'Role added successfully',
                    'data' => $resource,
                ], 201);
            }
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function delete_roles(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'id' => 'required|exists:roles,id',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            Role::where('id', $request->id)->delete();
            UserRole::where('role_id', $request->id)->delete();

            return response()->json([
                'message' => 'Role removed successfully',
            ], 200);
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_roles(Request $request)
    {
        try {
            $data = Role::orderby('created_at', 'asc')->get();

            if (count($data) > 0) {
                return response()->json([
                    'success' => true,
                    'message' => 'Role List',
                    'data' => RoleResource::collection($data),
                ], 200);
            } else {
                return response()->json([
                    'success' => false,
                    'message' => 'Data Not Found.',
                ], 404);
            }
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function permissions(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'permission_name' => 'required',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            if ($request->id != null) {
                $request_data = Permission::where('id', $request->id)->first();

                if (!$request_data) {
                    return response()->json([
                        'message' => 'Permission not found',
                    ], 404);
                }

                $input = $request->all();
                $request_data->permission_name = $input['permission_name'];
                $request_data->status = 'active';
                $request_data->updated_at = Carbon::now();

                $request_data->save();

                return response()->json([
                    'message' => 'Permission edited successfully',
                    'data' => new PermissionResource($request_data),
                ], 200);
            } else {
                $input = $request->all();
                $input['permission_name'] = $request['permission_name'];
                $input['status'] = 'active';

                $request_data = Permission::create($input);

                return response()->json([
                    'message' => 'Permission added successfully',
                    'data' => new PermissionResource($request_data),
                ], 201);
            }
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function delete_permissions(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'id' => 'required|exists:permissions,id',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            Permission::where('id', $request->id)->delete();

            return response()->json([
                'message' => 'Permission removed successfully',
            ], 200);
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_permissions(Request $request)
    {
        try {
            $data = Permission::where('status', 'active')->orderby('sequence_no', 'asc')->get();

            $resource = PermissionResource::collection($data);

            if (count($data) > 0) {
                return response()->json([
                    'message' => 'Permission List',
                    'data' => $resource,
                ], 200);
            } else {
                return response()->json([
                    'message' => 'Data Not Found.',
                ], 404);
            }
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function user_roles(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'user_id' => 'required|exists:users,id',
                'role_id' => 'required',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            UserRole::where('user_id', $request->user_id)->delete();

            $user_role_user = User::where('id', $request->user_id)->first();
            if (!$user_role_user) {
                return response()->json([
                    'message' => 'User not found',
                ], 404);
            }

            $user_role_user->role = $request->role_id;
            $user_role_user->save();

            $explode_role_ids = explode(',', $request->role_id);

            foreach ($explode_role_ids as $explode_role_id) {
                $input = $request->all();
                $input['user_id'] = $request['user_id'];
                $input['role_id'] = $explode_role_id;
                $input['status'] = 'active';

                $request_data = UserRole::create($input);
            }

            return response()->json([
                'success' => true,
                'message' => 'User Role added successfully',
                'data' => new UserRoleResource($request_data),
            ], 201);
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function delete_user_roles(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'id' => 'required|exists:user_roles,id',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            UserRole::where('id', $request->id)->delete();

            return response()->json([
                'message' => 'User Role removed successfully',
            ], 200);
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_user_roles(Request $request)
    {
        try {
            $data = UserRole::orderby('updated_at', 'desc')->get();

            if (count($data) > 0) {
                return response()->json([
                    'success' => true,
                    'message' => 'User Role List',
                    'data' => UserRoleResource::collection($data),
                ], 200);
            } else {
                return response()->json([
                    'success' => false,
                    'message' => 'Data Not Found.',
                ], 404);
            }
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function role_permissions(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'role_id' => 'required|exists:roles,id',
                'permission_id' => 'required',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            RolePermission::where('role_id', $request->role_id)->delete();

            $explode_permission_ids = explode(',', $request->permission_id);

            foreach ($explode_permission_ids as $explode_permission_id) {
                $input = $request->all();
                $input['role_id'] = $request['role_id'];
                $input['permission_id'] = $explode_permission_id;
                $input['status'] = 'active';

                $request_data = RolePermission::create($input);
            }

            return response()->json([
                'message' => 'Role Permission added successfully',
                'data' => new RolePermissionResource($request_data),
            ], 201);
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function delete_role_permissions(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'id' => 'required|exists:role_permissions,id',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            RolePermission::where('id', $request->id)->delete();

            return response()->json([
                'message' => 'Role Permission removed successfully',
            ], 200);
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_role_permissions(Request $request)
    {
        try {
            $data = RolePermission::orderBy('updated_at', 'desc')->get();

            if (count($data) > 0) {
                return response()->json([
                    'success' => true,
                    'message' => 'Role Permission List',
                    'data' => RolePermissionResource::collection($data),
                ], 200);
            } else {
                return response()->json([
                    'success' => false,
                    'message' => 'Data Not Found.',
                ], 404);
            }
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function permission_type(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'permission_type_name' => 'required',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            if ($request->id != null) {
                $request_data = PermissionType::findOrFail($request->id);

                $input = $request->all();
                $request_data->permission_type_name = $input['permission_type_name'];
                $request_data->status = 'active';
                $request_data->updated_at = Carbon::now();

                $request_data->save();

                $response_data = [
                    'success' => true,
                    'message' => 'Permission Type Edit Successfully',
                    'data' => new PermissionTypeResource($request_data),
                ];
            } else {
                $input = $request->all();
                $input['status'] = 'active';

                $request_data = PermissionType::create($input);

                $response_data = [
                    'message' => 'Permission Type Add Successfully',
                    'data' => new PermissionTypeResource($request_data),
                ];
            }

            return response()->json($response_data, 200);
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function delete_permission_type(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'id' => 'required|exists:permission_types,id',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            PermissionType::where('id', $request->id)->delete();

            return response()->json([
                'message' => 'Permission Type removed successfully',
            ], 200);
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_permission_type(Request $request)
    {
        try {
            $data = PermissionType::orderBy('updated_at', 'desc')->get();

            if (count($data) > 0) {
                return response()->json([
                    'message' => 'Permission Type List',
                    'data' => PermissionTypeResource::collection($data),
                ], 200);
            } else {
                return response()->json([
                    'message' => 'Data Not Found.',
                ], 404);
            }
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function permission_permission_type(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'permission_type_id' => 'required',
                'permission_id' => 'required',
            ]);

            if ($validator->fails()) {
                $response_data = [
                    'message' => 'Validation errors',
                    'errors' => $validator->errors(),
                ];
                return response()->json($response_data, 422);
            }

            PermissionPermissionType::where('permission_id', $request->permission_id)->delete();

            $explode_permission_ids = explode(',', $request->permission_type_id);

            foreach ($explode_permission_ids as $explode_permission_id) {
                $input = [
                    'permission_type_id' => $explode_permission_id,
                    'permission_id' => $request->permission_id,
                    'status' => 'active',
                ];

                $request_data = PermissionPermissionType::create($input);
            }

            $response_data = [
                'message' => 'Permission Permission Type Add Successfully',
                'data' => new PermissionPermissionTypeResource($request_data),
            ];

            return response()->json($response_data, 200);
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function delete_permission_permission_type(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'id' => 'required|exists:permission_permission_types,id',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            PermissionPermissionType::where('id', $request->id)->delete();

            return response()->json([
                'success' => true,
                'message' => 'Permission Permission Type removed successfully',
            ], 200);
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_permission_permission_type(Request $request)
    {
        try {
            $data = PermissionPermissionType::orderBy('updated_at', 'desc')->get();

            if (count($data) > 0) {
                return response()->json([
                    'message' => 'Permission Permission Type List',
                    'data' => PermissionPermissionTypeResource::collection($data),
                ], 200);
            } else {
                return response()->json([
                    'message' => 'Data Not Found.',
                ], 404);
            }
        } catch (Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_role_permission_by_user(Request $request)
    {
        try {
            // Retrieve user's role
            $User = UserRole::where('user_id', auth::id())->first();

            if (!$User) {
                throw new \Exception('User role not found.');
            }

            // Retrieve role with permissions
            $Role = Role::where('id', $User->role_id)->with('getPermission')->get();

            $FinalData = [];

            foreach ($Role as $role) {
                $Permissions = [];

                // Iterate through permissions
                foreach ($role->getPermission as $perm) {
                    $PermissionTypes = [];

                    // Retrieve permission types
                    $PermissionTypesQuery = PermissionPermissionType::leftJoin('permission_types', 'permission_types.id', '=', 'permission_permission_types.permission_type_id')
                        ->where('permission_id', $perm->id)
                        ->where('role_id', $role->id)
                        ->get();

                    $Permissions[] = [
                        'id' => $perm->id,
                        'permission_name' => $perm->permission_name,
                        'path' => $perm->path,
                        'icon' => $perm->icon,
                        'title' => $perm->permission_name,
                        'permission_types' => $PermissionTypesQuery->toArray()
                    ];
                }

                // Count active users with this role
                $role_count = UserRole::where('role_id', $role->id)->where('status', 'active')->count();

                $FinalData[] = [
                    'permissions' => $Permissions,
                    'role_count' => $role_count
                ];
            }

            // Prepare response data
            $response_data = [
                'success' => true,
                'message' => 'Role & Permission And Types',
                'data' => $Permissions
            ];

            return response()->json($response_data, 200); // HTTP 200 OK

        } catch (\Exception $e) {
            // Handle exceptions
            $response_data = [
                'success' => false,
                'message' => 'Error: ' . $e->getMessage(),
            ];
            return response()->json($response_data, 500); // HTTP 500 Internal Server Error
        }
    }

    public function get_role_permission_and_types(Request $request)
    {
        try {
            // Fetch all roles with their permissions
            $Role = Role::with('getPermission')->get();
            $FinalData = [];

            foreach ($Role as $role) {
                $Permissions = [];
                foreach ($role->getPermission as $perm) {
                    $PermissionTypes = [];

                    // Query for permission types associated with each permission
                    $PermissionTypesQuery = PermissionPermissionType::leftJoin('permission_types', 'permission_types.id', '=', 'permission_permission_types.permission_type_id')
                        ->where('permission_id', $perm->id)
                        ->where('role_id', $role->id)
                        ->get();

                    $Permissions[] = [
                        'id' => $perm->id,
                        'permission_name' => $perm->permission_name,
                        'permission_types' => $PermissionTypesQuery->toArray()
                    ];
                }

                // Count active users for each role
                $role_count = UserRole::where('role_id', $role->id)->where('status', 'active')->count();

                // Collect role data into FinalData array
                $FinalData[] = [
                    'id' => $role->id,
                    'role_name' => $role->role_name,
                    'permissions' => $Permissions,
                    'role_count' => $role_count
                ];
            }

            // Prepare response data
            $resource = $FinalData;

            if (count($FinalData) > 0) {
                return response()->json([
                    'message' => 'Role & Permission And Types',
                    'data' => $resource
                ], 200);
            } else {
                return response()->json([
                    'success' => false,
                    'message' => 'Data Not Found.',
                ], 404);
            }
        } catch (\Exception $e) {
            // Handle exceptions
            return response()->json([
                'success' => false,
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function add_role_with_per_and_type(Request $request)
    {
        try {
            // Assuming $this->successStatus is defined somewhere else in your controller

            // $request = Helper::request_data($request);
            $role_id = $request->role_id;
            $values = json_decode($request->values); // values = ["{\"permissionId\":9,\"typeId\":1}",]

            // Delete role permissions when new ones are inserted
            $get_permission_ids = RolePermission::where('role_id', $role_id)->pluck('permission_id');
            PermissionPermissionType::whereIn('permission_id', $get_permission_ids)->where('role_id', $role_id)->delete();
            RolePermission::where('role_id', $role_id)->delete();

            foreach ($values as $value) {
                $value_ = json_decode($value);
                $check_exists = RolePermission::where('role_id', $role_id)->where('permission_id', $value_->permissionId)->exists();

                if ($check_exists == false) {
                    $role_permission = [
                        'role_id' => $role_id,
                        'permission_id' => $value_->permissionId,
                    ];
                    RolePermission::create($role_permission);
                }

                $permission_type = [
                    'permission_id' => $value_->permissionId,
                    'permission_type_id' => $value_->typeId,
                    'role_id' => $role_id,
                ];

                PermissionPermissionType::create($permission_type);
            }

            $response_data = [
                'message' => 'Add Role Permission And Types',
            ];
            return response()->json($response_data, 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'An error occurred while adding role permissions and types.',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function team_status_change(Request $request)
    {
        try {
            // Validate incoming request
            $validator = Validator::make($request->all(), [
                'user_id' => 'required',
                'allow_rehire' => 'required',
                'status' => 'required',
                'reason_termination' => 'required',
            ]);

            if ($validator->fails()) {
                return response()->json([
                    'success' => false,
                    'message' => 'Validation error',
                    'errors' => $validator->errors(),
                ], 400); // Bad request
            }

            $user_id = $request->user_id;
            $allow_rehire = $request->allow_rehire;
            $status = $request->status;
            $reason_termination = $request->reason_termination;

            // Update user's status and other details
            $user = User::where('id', $user_id)->first();
            if (!$user) {
                return response()->json([
                    'success' => false,
                    'message' => 'User not found',
                ], 404); // Not found
            }

            $user->allow_rehire = $allow_rehire;
            $user->status = $status;
            $user->reason_termination = $reason_termination;
            $user->save();

            // Update user roles to 'terminated'
            $userRoles = UserRole::where('user_id', $user_id)->get();
            foreach ($userRoles as $userRole) {
                $userRole->status = 'terminated';
                $userRole->save();
            }

            // Send termination email
            $subject = 'Terminated';
            $email = $user->email;
            $body = 'Hi<br> ' . $user->name . '<br><br> We are sorry to inform you your account with Power of millions has been terminated, <br> For any query please contact <br><br> Regards,<br> Power of million team';

            Helper::sendemailcustom($subject, $email, $body);

            // Return success response with updated user data
            $data = User::where('id', $user_id)->first();
            return response()->json([
                'message' => 'Team Status Changed Successfully',
                'data' => new UserResource($data),
            ], 200); // Success
        } catch (\Exception $e) {
            // Handle exceptions
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500); // Internal server error
        }
    }

    public function resend_access(Request $request)
    {
        try {
            // Validate incoming request
            $validator = Validator::make($request->all(), [
                'user_id' => 'required',
            ]);

            if ($validator->fails()) {
                return response()->json([
                    'success' => false,
                    'message' => 'Validation error',
                    'errors' => $validator->errors(),
                ], 400); // Bad request
            }

            $user_id = $request->user_id;
            $random_password = Str::random(8);
            $hashed_password = Hash::make($random_password);

            // Retrieve user details
            $user = User::where('id', $user_id)->first();
            if (!$user) {
                return response()->json([
                    'success' => false,
                    'message' => 'User not found',
                ], 404); // Not found
            }

            // Update password and account status based on user status
            if ($user->status == 'terminated') {
                // Reactivate terminated account
                $user->status = 'active';
                $user->password = $hashed_password;
                $user->save();

                $subject = 'Resend Access';
                $body = 'Hi<br> ' . $user->name . '<br><br> Congratulations! Welcome back to Power of millions. Here are your login credentials:<br><br> Email: ' . $user->email . '<br> Password: ' . $random_password . '<br><br> Regards,<br> Power of million team';

                Helper::sendemailcustom($subject, $user->email, $body);
            } else {
                // User is active, just update password
                $user->password = $hashed_password;
                $user->save();

                $subject = 'Resend Access';
                $body = 'Hi<br> ' . $user->name . '<br><br> Here are your login credentials:<br><br> Email: ' . $user->email . '<br> Password: ' . $random_password . '<br><br> Regards,<br> Power of million team';

                Helper::sendemailcustom($subject, $user->email, $body);
            }

            // Fetch updated user data
            $data = User::where('id', $user_id)->first();
            if ($data) {
                return response()->json([
                    'message' => 'Resend Access Successfully',
                    'data' => new UserResource($data),
                ], 200); // Success
            } else {
                return response()->json([
                    'message' => 'Data Not Found.',
                ], 404); // Not found
            }
        } catch (\Exception $e) {
            // Handle exceptions
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500); // Internal server error
        }
    }
}
