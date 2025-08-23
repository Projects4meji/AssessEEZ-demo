<?php

namespace App\Http\Controllers\API;

use App\Http\Controllers\Controller;
use App\Http\Helpers\Helper;
use App\Http\Resources\IQAReportResource;
use App\Http\Resources\MinutesOfMeetingResource;
use App\Models\ResourceMaterial;
use App\Models\ResourceMaterialCohortBatch;
use App\Models\ResourceMaterialQualification;
use App\Models\ResourceMaterialRole;
use Carbon\Carbon;
use GuzzleHttp\Client;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Facades\Validator;
use Illuminate\Support\Str;
use App\Http\Resources\ResourceMaterialResource;
use App\Models\IqaReport;
use App\Models\MinutesOfMeeting;
use App\Models\MinutesOfMeetingAttachement;
use App\Models\User;
use App\Models\UserQualification;
use Illuminate\Support\Facades\DB;


class ResourceMaterialController extends Controller
{

    // public function get_cohort_batch(Request $request) {

    //     $qualifications = null;
    //     if($request->qualification_ids != null) {
    //         $qualifications = explode(',', $request->qualification_ids);
    //     }


    //     $cohortBatch = User::where('role_id', '3')->select('');
    // }


    public function save_iqa_report(Request $request) {

        $validator = Validator::make($request->all(), [
            'date' => 'required',
            'title' => 'required',
            'qualification_id' => 'required',
            // 'assessor_id' => 'required',
            // 'learner_id' => 'required',
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
        try {

            if($request->assessor_id == null && $request->learner_id == null) {
                return response()->json([
                    'message' => 'Please select assessor or iqa!',
                    'error' => 'Please select assessor or iqa!'
                ], 422);
            }

            $iqa_report = [
                'date' =>  $request->date,
                'title' =>  $request->title,
                'qualification_id' => $request->qualification_id,
                'assessor_id' => $request->assessor_id ?? null,
                'learner_id' => $request->learner_id ?? null,
                'created_by' => Auth::id(),
                'updated_by' => Auth::id(),
            ];

            $response = IqaReport::create($iqa_report);

            if ($request->file('file')) {
                $extension = $request->file('file')->extension();
                $attachement = $request->file('file');
                $url = Str::random(20) . '.' . $extension;

                $basic_url = 'iqa_reports/' . Auth::id();
                $path = ($basic_url . "/" . $url);
                Helper::FileUpload($path, $attachement);

                $response->attachement = $url;
                $response->save();
            } 

            return response()->json([
                'message' => 'IQA Report Create successfully.',
            ], 201);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'IQA Report Creation failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }
    
    public function get_iqa_report(Request $request)
    {
        $iqa_report = IqaReport::query();

        if ($request->has('search')) {
            $search = $request->input('search');
            
            $iqaReport_ = IqaReport::where(function ($query) use ($search) {
                $query->where('date', 'LIKE', '%' . $search . '%');
            })->pluck('id');

            $iqa_report->whereIn('id', $iqaReport_);
        }

        $auth_ = (int)Auth::user()->role_id;

        if($request->user_id != null && $request->qualification_id != null) {
            $iqa_report = $iqa_report->where('qualification_id', $request->qualification_id)->where('learner_id', $request->user_id);
        } else {
            if($auth_ == 4) {
                $iqa_report = $iqa_report->where('assessor_id', Auth::id());
            } else {                
                if($auth_ == 2 || $auth_ == 6) {
                    $users_ = User::whereIn('created_by', Helper::getAdmin_ids(Auth::id()))->where('role_id', '5')->pluck('id');
                    $iqa_report = $iqa_report->whereIn('created_by', $users_);
                } else {
                    $iqa_report = $iqa_report->where('created_by', Auth::id());
                }

                //Filter With Qualifications
                if($request->has('parent_qualification_id')) {
                    $iqa_report = $iqa_report->where('qualification_id', $request->parent_qualification_id);
                }

                //Filter With Type (Assessors Or Learners)
                if($request->has('type')) {
                    if($request->type == "Learners") {
                        $iqa_report = $iqa_report->whereNotNull('learner_id');
                    } else {
                        $iqa_report = $iqa_report->whereNotNull('assessor_id');
                    }                    
                }
            }
        }
        
        $iqa_report = $iqa_report->orderby('id', 'desc');
        $count = $iqa_report->count();

        if ($request->has('page')) {
            $data = $iqa_report->paginate(10);
        } else {
            $data = $iqa_report->get();
        }

        if ($data->isEmpty()) {
            return response()->json(['error' => 'No record found.'], 404);
        }

        return response()->json([
            'message' => 'IQA Report List',
            'data' => IQAReportResource::collection($data),
            'count' => $count
        ], 200);
    }

    public function save_minutes_of_meetings(Request $request) {

        $validator = Validator::make($request->all(), [
            'date' => 'required',
            'type' => 'required',
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
        try {            

            if ($request->file('file')) {

                $minutes_of_meetings = [
                    'date' =>  $request->date,
                    'type' => $request->type,
                    // 'attachement' => $url,
                    'created_by' => Auth::id(),
                    'updated_by' => Auth::id(),
                    'title' => $request->title,
                ];
    
                $response = MinutesOfMeeting::create($minutes_of_meetings);

                foreach ($request->file as $curr_file) {
                    $extension = $curr_file->extension();
                    $attachement = $curr_file;
                    $url = Str::random(20) . '.' . $extension;
                    
                    $path = "minutes_of_meetings/" . Auth::id() . "/" . $url;
                    Helper::FileUpload($path, $attachement);                
                
                    $meeting_attachements = [
                        'meeting_id' =>  $response->id,
                        'attachement' => $url,
                        'created_by' => Auth::id(),
                        'updated_by' => Auth::id(),
                    ];
        
                    $attachement_response = MinutesOfMeetingAttachement::create($meeting_attachements);
                }
            } 

            return response()->json([
                'message' => 'Minutes of Meetings Create successfully.',
            ], 201);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Minutes of Meetings Creation failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_minutes_of_meetings(Request $request)
    {
        $minutes_of_meetings = MinutesOfMeeting::query();

        if ($request->has('search')) {
            $search = $request->input('search');

            $searchResult = MinutesOfMeeting::where(function ($query) use ($search) {
                $query->where('date', 'LIKE', '%' . $search . '%');
            })->pluck('id');

            $minutes_of_meetings->whereIn('id', $searchResult);
        }
        
        $authUser = Auth::user();

        if((int)$authUser->role_id == 2 || (int)$authUser->role_id == 6) {
            $iqaUserList = User::whereIn('created_by', Helper::getAdmin_ids((int)$authUser->id))->where('role_id', '5')->pluck('id');
            $minutes_of_meetings = $minutes_of_meetings->whereIn('created_by', $iqaUserList);  
        } else {
            $minutes_of_meetings = $minutes_of_meetings->where('created_by', Auth::id());  
        }

        //$minutes_of_meetings = $minutes_of_meetings->where('created_by', Auth::id());


        $count = $minutes_of_meetings->count();

        if ($request->has('page')) {
            $data = $minutes_of_meetings->paginate(10);
        } else {
            $data = $minutes_of_meetings->get();
        }

        if ($data->isEmpty()) {
            return response()->json(['error' => 'No record found.'], 404);
        }

        return response()->json([
            'message' => 'Minutes of Meetings List',
            'data' => MinutesOfMeetingResource::collection($data),
            'count' => $count
        ], 200);
    }

    public function save_resource_materail(Request $request)
    {
        if ($request->folder_id == null) {
            $validator = Validator::make($request->all(), [
                'folder_name' => 'required',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            try {
                $resourse_materials = ResourceMaterial::whereIn('created_by', Helper::getAdmin_ids(Auth::id()))
                    ->where('folder_name', $request->folder_name)
                    ->first();

                if ($resourse_materials != null) {
                    return response()->json([
                        'message' => 'Folder already exist!'
                    ], 422);
                }

                $resource_material = [
                    'folder_name' =>  $request->folder_name,
                    'status' => 'active',
                    'created_by' => Auth::id(),
                    'updated_by' => Auth::id(),
                ];

                $resource = ResourceMaterial::create($resource_material);

                return response()->json([
                    'message' => 'File Create successfully.',
                ], 201);
            } catch (\Exception $e) {
                // DB::rollbackTransaction();
                return response()->json([
                    'message' => 'Folder Creation failed',
                    'error' => $e->getMessage(),
                ], 500);
            }
        }

        $validator = Validator::make($request->all(), [
            'folder_id' => 'required',
            'file_name' => 'required',
            'file_type' => 'required',
            'qualification_ids' => 'required',
            'role_ids' => 'required',
            'file_url' => 'required',
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

        if($request->qualification_ids == "[]") {
            return response()->json([
                'message' => 'Please select qualification!',                
            ], 422);
        }

        if($request->role_ids == "[]") {
            return response()->json([
                'message' => 'Please select role!',
            ], 422);
        }

        if($request->file_type == "file" && $request->file == null) {
            return response()->json([
                'message' => 'Please select file!',
            ], 422);
        } else if ($request->file_type != "file" && ($request->file_url == null || $request->file_url == "0")) {
            return response()->json([
                'message' => 'Please select file url!',
            ], 422);
        }

        try {
            $resourse_materials = ResourceMaterial::whereIn('created_by', Helper::getAdmin_ids(Auth::id()))
                ->where('folder_id', $request->folder_id)
                ->where('file_name', $request->file_name)
                ->first();

            if ($resourse_materials != null) {
                return response()->json([
                    'message' => 'File already exist!'
                ], 422);
            }

            // DB::beginTransaction();

            $resource_material = [
                'folder_id' =>  $request->folder_id,
                'file_name' => $request->file_name,
                'file_type' => $request->file_type,
                'status' => 'active',
                'created_by' => Auth::id(),
                'updated_by' => Auth::id(),
            ];

            $resource = ResourceMaterial::create($resource_material);

            if ($request->file('file') && $request->file_type == "file") {
                $extension = $request->file('file')->extension();
                $attachement = $request->file('file');
                $url = Str::random(20) . '.' . $extension;


                // Storage::disk('local')->put(
                //     '/public/' . Auth::id() . "/" . $request->folder_name . '/' . $url,
                //     File::get($attachement)
                // );

                $folder_name = ResourceMaterial::where('id', $request->folder_id)->first();

                $path = "resource_materials/" . Auth::id() . ($folder_name != null ? "/" . $folder_name->folder_name : "") . "/" . $url;

                Helper::FileUpload($path, $attachement);

                $resource->file = $url;
                $resource->save();

                // chmod(storage_path('app/public/' . Auth::id()), 0775);
                // chmod(storage_path('app/public/' . Auth::id() . "/" . $request->folder_name), 0775);
                // chmod(storage_path('app/public/' . Auth::id() . "/" . $request->folder_name . '/' . $url), 0775);
            } else {
                $resource->file = $request->file_url;
                $resource->save();
            }

            //Resource Material Qualifications
            if ($request->qualification_ids != null) {
                $qualifications = json_decode($request->qualification_ids, true);

                foreach ($qualifications as $qualification) {
                    $qualification_record = [
                        'resource_material_id' => $resource->id,
                        'qualification_id' => $qualification,
                        'status' => 'active',
                        'created_by' => Auth::id(),
                        'updated_by' => Auth::id(),
                    ];

                    ResourceMaterialQualification::create($qualification_record);
                }
            }

            //Resource Material Roles
            if ($request->role_ids != null) {
                $roles = json_decode($request->role_ids, true);

                foreach ($roles as $role) {
                    $role_record = [
                        'resource_material_id' => $resource->id,
                        'role_id' => $role,
                        'status' => 'active',
                        'created_by' => Auth::id(),
                        'updated_by' => Auth::id(),
                    ];

                    ResourceMaterialRole::create($role_record);
                }
            }

            //Resource Material Cohort/Batch
            if ($request->batch_numbers != null) {
                $batches = json_decode($request->batch_numbers, true);

                foreach ($batches as $batch) {
                    $batch_record = [
                        'resource_material_id' => $resource->id,
                        'cohort_batch_no' => $batch,
                        'status' => 'active',
                        'created_by' => Auth::id(),
                        'updated_by' => Auth::id(),
                    ];

                    ResourceMaterialCohortBatch::create($batch_record);
                }
            }

            // DB::commitTransaction();
            return response()->json([
                'message' => 'File Create successfully.',
            ], 201);
        } catch (\Exception $e) {
            // DB::rollbackTransaction();
            return response()->json([
                'message' => 'File Creation failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function edit_resource_materail(Request $request)
    {

        if ($request->folder_id == null) {
            $validator = Validator::make($request->all(), [
                'id' => 'required',
                'folder_name' => 'required',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            try {
                $resourse_materials = ResourceMaterial::whereIn('created_by', Helper::getAdmin_ids(Auth::id()))
                    ->where('folder_name', $request->folder_name)
                    ->where('id', '!=', $request->id)
                    ->first();

                if ($resourse_materials != null) {
                    return response()->json([
                        'message' => 'Folder already exist!'
                    ], 422);
                }

                $resource = ResourceMaterial::where('id', $request->id)->whereNull('folder_id')->first();
                $resource->folder_name = $request->folder_name;
                $resource->updated_by = Auth::id();
                $resource->save();

                return response()->json([
                    'message' => 'Folder Edited successfully.',
                ], 201);
            } catch (\Exception $e) {
                // DB::rollbackTransaction();
                return response()->json([
                    'message' => 'Folder Edit failed',
                    'error' => $e->getMessage(),
                ], 500);
            }
        }


        $validator = Validator::make($request->all(), [
            'id' => 'required',
            'folder_id' => 'required',
            'file_name' => 'required',
            'file_type' => 'required',
            'qualification_ids' => 'required',
            'role_ids' => 'required',
            'file_url' => 'required',
            'file' => 'max:2048',
        ], [
            'file.max' => 'The file size must not exceed 2 MB.',
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        if($request->qualification_ids == "[]") {
            return response()->json([
                'message' => 'Please select qualification!',                
            ], 422);
        }

        if($request->role_ids == "[]") {
            return response()->json([
                'message' => 'Please select role!',
            ], 422);
        }

        if($request->file_type == "file" && $request->file == null) {
            return response()->json([
                'message' => 'Please select file!',
            ], 422);
        } else if ($request->file_type != "file" && ($request->file_url == null || $request->file_url == "0")) {
            return response()->json([
                'message' => 'Please select file url!',
            ], 422);
        }

        try {
            $resourse_materials = ResourceMaterial::whereIn('created_by', Helper::getAdmin_ids(Auth::id()))
                ->where('folder_id', $request->folder_id)
                ->where('file_name', $request->file_name)
                ->where('id', '!=', $request->id)
                ->first();

            if ($resourse_materials != null) {
                return response()->json([
                    'message' => 'File already exist!'
                ], 422);
            }

            // DB::beginTransaction();

            $resource = ResourceMaterial::where('id', $request->id)->first();
            $resource->folder_id = $request->folder_id;
            $resource->file_name = $request->file_name;
            $resource->file_type = $request->file_type;
            // $resource->created_by = Auth::id();
            $resource->updated_by = Auth::id();

            if ($request->file('file') && $request->file_type == "file") {
                $extension = $request->file('file')->extension();
                $attachement = $request->file('file');
                $url = Str::random(20) . '.' . $extension;
                
                $folder_name = ResourceMaterial::where('id', $request->folder_id)->first();

                // $path = "resource_materials/" . Auth::id() . "/" . $request->folder_name . "/" . $url;
                $path = "resource_materials/" . Auth::id() . ($folder_name != null ? "/" . $folder_name->folder_name : "") . "/" . $url;

                // Storage::disk('local')->put(
                //     '/public/' . Auth::id() . "/" . $request->folder_name . '/' . $url,
                //     File::get($attachement)
                // );
                Helper::FileUpload($path, $attachement);
                
                
                $resource->file = $url;
                $resource->save();

                // chmod(storage_path('app/public/' . Auth::id()), 0775);
                // chmod(storage_path('app/public/' . Auth::id() . "/" . $request->folder_name), 0775);
                // chmod(storage_path('app/public/' . Auth::id() . "/" . $request->folder_name . '/' . $url), 0775);
            } else {
                $resource->file = $request->file_url;
                $resource->save();
            }

            //Resource Material Qualifications
            if ($request->qualification_ids != null) {
                ResourceMaterialQualification::where('resource_material_id', $resource->id)->delete();
                $qualifications = json_decode($request->qualification_ids, true);

                foreach ($qualifications as $qualification) {
                    $qualification_record = [
                        'resource_material_id' => $resource->id,
                        'qualification_id' => $qualification,
                        'status' => 'active',
                        'created_by' => Auth::id(),
                        'updated_by' => Auth::id(),
                    ];

                    ResourceMaterialQualification::create($qualification_record);
                }
            }

            //Resource Material Roles
            if ($request->role_ids != null) {
                ResourceMaterialRole::where('resource_material_id', $resource->id)->delete();
                $roles = json_decode($request->role_ids, true);

                foreach ($roles as $role) {
                    $role_record = [
                        'resource_material_id' => $resource->id,
                        'role_id' => $role,
                        'status' => 'active',
                        'created_by' => Auth::id(),
                        'updated_by' => Auth::id(),
                    ];

                    ResourceMaterialRole::create($role_record);
                }
            }

            //Resource Material Cohort/Batch
            if ($request->batch_numbers != null) {
                ResourceMaterialCohortBatch::where('resource_material_id', $resource->id)->delete();
                $batches = json_decode($request->batch_numbers, true);

                foreach ($batches as $batch) {
                    $batch_record = [
                        'resource_material_id' => $resource->id,
                        'cohort_batch_no' => $batch,
                        'status' => 'active',
                        'created_by' => Auth::id(),
                        'updated_by' => Auth::id(),
                    ];

                    ResourceMaterialCohortBatch::create($batch_record);
                }
            }

            // DB::commitTransaction();
            return response()->json([
                'message' => 'File edited successfully.',
            ], 201);
        } catch (\Exception $e) {
            // DB::rollbackTransaction();
            return response()->json([
                'message' => 'File edit failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_resource_materail(Request $request)
    {
        $resourse_materials = ResourceMaterial::query();

        // if ($request->folder_id) {
        //     $resourse_materials->where('folder_id', $request->folder_id);            
        // }

        if ($request->has('search')) {
            $search = $request->input('search');
            $searchResult = ResourceMaterial::where(function ($query) use ($search) {
                $query->where('folder_name', 'LIKE', '%' . $search . '%')
                    ->orWhere('file_name', 'LIKE', '%' . $search . '%');
            })->pluck('id');

            $resourse_materials->whereIn('id', $searchResult);

        }

        if ($request->id != null && $request->folder_id == null) {
            $resourse_materials->where('id', $request->id);
        } else if ($request->id != null && $request->folder_id != null) {
            $resourse_materials->where('id', $request->folder_id);
        }

        $roleId = (int)Auth::user()->role_id;


        $resourse_materials = $resourse_materials->whereIn('created_by', Helper::getAdmin_ids(($roleId == 2 || $roleId == 6) ? Auth::id() : $request->company_admin_id));
        
        if($roleId > 2 && $roleId != 6) {
            //Qualification Filter
            $userQualifications = UserQualification::where('user_id', Auth::id())->pluck('qualification_id');
            $resourceMaterialQualifications = ResourceMaterialQualification::whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id));
            if($request->qualification_id != null) {
                $resourceMaterialQualifications = $resourceMaterialQualifications->where('qualification_id', $request->qualification_id)->pluck('resource_material_id');
            } else {
                $resourceMaterialQualifications = $resourceMaterialQualifications->whereIn('qualification_id', $userQualifications)->pluck('resource_material_id');
            }            

            $qualification_resourceMat_ = ResourceMaterial::whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id))
            ->whereIn('id', $resourceMaterialQualifications);            
            
            ////////////////////$resourse_materials = $resourse_materials->whereIn('id', $qualification_resourceMat_);

            //Role Filter
            $resourceMaterialRoles = ResourceMaterialRole::whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id))
            ->where('role_id', $roleId)->pluck('resource_material_id');

            $qualification_resourceMat_ = $qualification_resourceMat_->whereIn('id', $resourceMaterialRoles)->pluck('folder_id');

            $resourse_materials = $resourse_materials->whereIn('id', $qualification_resourceMat_);

            // $role_resourceMat_ = ResourceMaterial::whereIn('id', $resourceMaterialRoles)->pluck('folder_id');
            // $resourse_materials = $resourse_materials->whereIn('id', $role_resourceMat_);
        }
        
        $resourse_materials = $resourse_materials->whereNull('folder_id')
            ->select('created_by', 'folder_name', 'id', DB::raw(($request->id != null && $request->folder_id != null ? $request->id : 0) . ' as child_id'))
            ->distinct('created_by', 'folder_name', 'id')->get();

        if (count($resourse_materials) <= 0) {
            return response()->json(['error' => 'No record found.'], 404);
        }

        return response()->json([
            'message' => 'Resource material list',
            'data' => ResourceMaterialResource::collection($resourse_materials)
        ], 200);
    }

    public function delete_resource_materail(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'id' => 'required|exists:resource_materials,id',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            ResourceMaterial::where('id', $request->id)->delete();
            ResourceMaterialCohortBatch::where('resource_material_id', $request->id)->delete();
            ResourceMaterialQualification::where('resource_material_id', $request->id)->delete();
            ResourceMaterialRole::where('resource_material_id', $request->id)->delete();

            return response()->json([
                'message' => 'Deleted successfully',
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }
}
