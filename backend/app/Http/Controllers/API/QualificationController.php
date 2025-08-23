<?php

namespace App\Http\Controllers\API;

use App\Http\Controllers\Controller;
use App\Http\Helpers\Helper;
use App\Http\Resources\AssessorFeedbackResource;
use App\Http\Resources\IQACommentResource;
use App\Http\Resources\QualificationResource;
use App\Http\Resources\QualificationSubmissionResource;
use App\Http\Resources\QualificationACSResource;
use App\Http\Resources\QualificationDetailResource;
use App\Http\Resources\SubmissionDetailResource;
use App\Http\Resources\QualificationDocumentResource;
use App\Http\Resources\QualificationDropdownResource_V1;
use App\Http\Resources\QualificationResource_V1;
use App\Http\Resources\QualificationSubmissionResource_V2;
use App\Http\Resources\QualificationSubmissionResource_V3;
use App\Http\Resources\SuperAdminQualificationResource;
use App\Http\Resources\SuperAdminQualificationResourceV1;
use App\Http\Resources\UserDropdownResource_V1;
use App\Http\Resources\UserQualificationResource;
use App\Http\Resources\UserResource;
use App\Http\Resources\UserResource_V1;
use App\Models\AssessorFeedback;
use App\Models\IqaComment;
use App\Models\Order;
use App\Models\Otp;
use App\Models\Product;
use App\Models\Qualification;
use App\Models\QualificationAc;
use App\Models\QualificationDocument;
use App\Models\QualificationDocumentTitle;
use App\Models\QualificationLo;
use App\Models\QualificationSubmission;
use App\Models\QualificationUnit;
use App\Models\RequestPayment;
use App\Models\SubmissionAttachement;
use App\Models\User;
use App\Models\UserAssessor;
use App\Models\UserQualification;
use Carbon\Carbon;
use GuzzleHttp\Client;
use Illuminate\Http\Request;
use Illuminate\Support\Arr;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Facades\Validator;
use Illuminate\Support\Str;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;
use PHPUnit\TextUI\Help;

class QualificationController extends Controller
{
    public function save_qualification(Request $request)
    {
        $validator = Validator::make($request->all(), [
            // 'sub_title' => 'required|string|max:255|unique:qualifications,sub_title',
            // 'sub_number' => 'required|string|max:255|unique:qualifications,sub_number',
            'units' => 'required',
            'unit_document_titles' => 'required',
            'sub_title' => [
                'required',
                Rule::unique('qualifications')->whereIn('created_by', Helper::getAdmin_ids(Auth::id()))->whereNull('deleted_at'),
            ],
            'sub_number' => [
                'required',
                Rule::unique('qualifications')->whereIn('created_by', Helper::getAdmin_ids(Auth::id()))->whereNull('deleted_at'),
            ],
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        try {

            $qualification_id_ = null;

            $qualificationData = [
                'sub_title' => $request->sub_title ?? null,
                'sub_number' => $request->sub_number ?? null,
                'status' => 'active',
                'created_by' => Auth::id(),
                'updated_by' => Auth::id()
            ];

            $qualification =  Qualification::create($qualificationData);
            $qualification_id_ = $qualification->id;

            if ($request->units != null) {
                $units = json_decode($request->units, true);
                $qualificationId = $qualification ? $qualification->id : 0;

                foreach ($units as $unitData) {
                    $unitTitle = $unitData['unit_title'];
                    $unitNumber = $unitData['unit_number'];

                    // Check if the unit title already exists for the same qualification
                    $unitExists = QualificationUnit::where('qualification_id', $qualificationId)
                        ->where('unit_title', $unitTitle)
                        // ->where('unit_number', $unitNumber)
                        ->exists();

                    if ($unitExists) {
                        if($qualification_id_ != null) {
                            DB::table('qualifications')->where('id', $qualification_id_)->delete();
                            DB::table('qualification_units')->where('qualification_id', $qualification_id_)->delete();
                            DB::table('qualification_los')->where('qualification_id', $qualification_id_)->delete();
                            DB::table('qualification_acs')->where('qualification_id', $qualification_id_)->delete();
                        }

                        return response()->json([
                            'message' => 'Validation errors',
                            'error' => "Unit title already exists in this qualification."
                        ], 422);
                    }

                    $unit = QualificationUnit::create([
                        'qualification_id' => $qualification ? $qualification->id : 0,
                        'unit_number' => $unitData['unit_number'],
                        'unit_title' => $unitData['unit_title'],
                        'unit_type_id' => $unitData['unit_type_id'],
                        'status' => 'active',
                        'created_by' => Auth::id(),
                        'updated_by' => Auth::id()
                    ]);

                    foreach ($unitData['LO'] as $loData) {
                        $lo_detail = $loData['lo_detail'];

                        $loExists = QualificationLo::where('qualification_id', $qualificationId)
                            ->where('lo_detail', $lo_detail)
                            ->exists();

                        if ($loExists) {

                            if($qualification_id_ != null) {
                                DB::table('qualifications')->where('id', $qualification_id_)->delete();
                                DB::table('qualification_units')->where('qualification_id', $qualification_id_)->delete();
                                DB::table('qualification_los')->where('qualification_id', $qualification_id_)->delete();
                                DB::table('qualification_acs')->where('qualification_id', $qualification_id_)->delete();
                            }

                            return response()->json([
                                'message' => 'Validation errors',
                                'error' => "LO detail already exists in this qualification."
                            ], 422);
                        }

                        $lo = QualificationLo::create([
                            'qualification_id' => $qualification ? $qualification->id : 0,
                            'unit_id' => $unit ? $unit->id : 0,
                            'lo_number' => $loData['lo_number'],
                            'lo_detail' => $loData['lo_detail'],
                            'status' => 'active',
                            'created_by' => Auth::id(),
                            'updated_by' => Auth::id()
                        ]);

                        foreach ($loData['AC'] as $acData) {

                            $ac_detail = $acData['ac_detail'];

                            $loExists = QualificationAc::where('qualification_id', $qualificationId)
                                ->where('ac_detail', $ac_detail)
                                ->exists();

                            if ($loExists) {

                                if($qualification_id_ != null) {
                                    DB::table('qualifications')->where('id', $qualification_id_)->delete();
                                    DB::table('qualification_units')->where('qualification_id', $qualification_id_)->delete();
                                    DB::table('qualification_los')->where('qualification_id', $qualification_id_)->delete();
                                    DB::table('qualification_acs')->where('qualification_id', $qualification_id_)->delete();
                                }

                                return response()->json([
                                    'message' => 'Validation errors',
                                    'error' => "AC detail already exists in this qualification."
                                ], 422);
                            }

                            QualificationAc::create([
                                'qualification_id' => $qualification ? $qualification->id : 0,
                                'lo_id' => $lo ? $lo->id : 0,
                                'ac_number' => $acData['ac_number'],
                                'ac_detail' => $acData['ac_detail'],
                                'status' => 'active',
                                'created_by' => Auth::id(),
                                'updated_by' => Auth::id()
                            ]);
                        }
                    }
                }
            }

            if ($request->unit_document_titles != null) {
                $unit_document_titles = json_decode($request->unit_document_titles, true);

                foreach ($unit_document_titles as $unit_document_title) {

                    $title = $unit_document_title['title'];

                    $loExists = QualificationDocumentTitle::where('qualification_id', $qualificationId)
                        ->where('title', $title)
                        ->exists();

                    if ($loExists) {
                        if($qualification_id_ != null) {
                            DB::table('qualifications')->where('id', $qualification_id_)->delete();
                            DB::table('qualification_units')->where('qualification_id', $qualification_id_)->delete();
                            DB::table('qualification_los')->where('qualification_id', $qualification_id_)->delete();
                            DB::table('qualification_acs')->where('qualification_id', $qualification_id_)->delete();
                            DB::table('qualification_document_titles')->where('qualification_id', $qualification_id_)->delete();
                        }

                        return response()->json([
                            'message' => 'Validation errors',
                            'error' => "Document title already exists in this qualification."
                        ], 422);
                    }

                    $unit = QualificationDocumentTitle::create([
                        'qualification_id' => $qualification ? $qualification->id : 0,
                        'title' => $unit_document_title['title'],
                        'status' => 'active',
                        'created_by' => Auth::id(),
                        'updated_by' => Auth::id()
                    ]);
                }
            }

            return response()->json([
                'message' => 'Created successfully.',
            ], 201);
        } catch (\Exception $e) {

            if($qualification_id_ != null) {
                DB::table('qualifications')->where('id', $qualification_id_)->delete();
                DB::table('qualification_units')->where('qualification_id', $qualification_id_)->delete();
                DB::table('qualification_los')->where('qualification_id', $qualification_id_)->delete();
                DB::table('qualification_acs')->where('qualification_id', $qualification_id_)->delete();
                DB::table('qualification_document_titles')->where('qualification_id', $qualification_id_)->delete();
            }

            return response()->json([
                'message' => 'Creation failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function update_qualification(Request $request)
    {
        $validator = Validator::make($request->all(), [

            'sub_title' => 'required|string|max:255',
            'sub_number' => 'required|string|max:255',
            'units' => 'required',
            'unit_document_titles' => 'required',
            'id' => 'required|exists:qualifications,id',
            // ,
            // 'sub_number' => [
            //     'required',
            //     'string',
            //     'max:255',
            // ],
        ]);        

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }
        
        try {
            //Check Qualification Sub Title
            $qualification_ = Qualification::whereIn('created_by', Helper::getAdmin_ids(Auth::id()))->where('id', '!=', $request->id)
            ->where('sub_title', $request->sub_title)->whereNull('deleted_at')->first();

            if($qualification_ != null) {
                return response()->json([
                        'message' => 'Validation errors',
                        'error' => 'The sub title has already been taken.'
                ], 422);
            }

            //Check Qualification Sub Number
            $qualification_ = Qualification::whereIn('created_by', Helper::getAdmin_ids(Auth::id()))->where('id', '!=', $request->id)
            ->where('sub_number', $request->sub_number)->whereNull('deleted_at')->first();

            if($qualification_ != null) {
                return response()->json([
                        'message' => 'Validation errors',
                        'error' => 'The sub number has already been taken.'
                ], 422);
            }

            

            //Validate Unit, LO, AC
            if ($request->units != null) 
            {            
                $units_validate = json_decode($request->units, true);
                foreach ($units_validate as $unitData) {
                    $unit_validatation = QualificationUnit::where('qualification_id', $request->id);                
                        if (Arr::has($unitData, 'id')) {
                            $unit_validatation = $unit_validatation->where('id', '!=', $unitData['id']);
                        }
                    $unit_validatation = $unit_validatation->where('unit_title', $unitData['unit_title'])
                    ->first();

                    if($unit_validatation != null) {
                        return response()->json([
                                        'message' => 'Validation errors',
                                        'error' => 'Unit title already been taken in this qualification!'
                                    ], 422);
                    }

                    //Validate Learning Outcome
                    foreach ($unitData['LO'] as $loData) {
                        $lo_validatation = QualificationLo::where('qualification_id', $request->id);                    
                            if (Arr::has($loData, 'id')) {
                                $lo_validatation = $lo_validatation->where('id', '!=', $loData['id']);
                            }
                            $lo_validatation = $lo_validatation->where('lo_detail', $loData['lo_detail'])                    
                        ->first();

                        if($lo_validatation != null) {
                            return response()->json([
                                            'message' => 'Validation errors',
                                            'error' => 'Learning outcome already been taken in this qualification!'
                                        ], 422);
                        }

                        //Validate Assessment Criterion
                        foreach ($loData['AC'] as $acData) {
                            $ac_validatation = QualificationAc::where('qualification_id', $request->id);
                                if (Arr::has($acData, 'id')) {
                                    $ac_validatation = $ac_validatation->where('id', '!=', $acData['id']);
                                }
                                $ac_validatation = $ac_validatation->where('ac_detail', $acData['ac_detail'])
                            ->first();

                            if($ac_validatation != null) {
                                return response()->json([
                                                'message' => 'Validation errors',
                                                'error' => 'Assessment Criterion already been taken in this qualification!'
                                            ], 422);
                            }                        
                        }

                    }
                }
            }

            //Validate Learner's Documents
            if ($request->unit_document_titles != null) {
                $document_validate = json_decode($request->unit_document_titles, true);
                foreach($document_validate as $unit_document_title) {

                    $doc_validatation = QualificationDocumentTitle::where('qualification_id', $request->id);
                        if (Arr::has($unit_document_title, 'id')) {
                            $doc_validatation = $doc_validatation->where('id', '!=', $unit_document_title['id']);
                        }
                    $doc_validatation = $doc_validatation->where('title', $unit_document_title['title'])
                    ->first();                    

                    if($doc_validatation != null) {
                        return response()->json([
                                        'message' => 'Validation errors',
                                        'error' => 'Document title already been taken in this qualification!'
                                    ], 422);
                    }

                }
            }


            $qualification = Qualification::where('id', $request->id)->first();
            $qualification->sub_title = $request->sub_title ?? null;
            $qualification->sub_number = $request->sub_number ?? null;
            // $qualification->created_by = Auth::id();
            $qualification->updated_by = Auth::id();
            $qualification->save();

            $dummy = null;

            

            if ($request->units != null) {

                $units = json_decode($request->units, true);
                
                // $newUnit_ = array_column($units, 'id');

                // $submissions_ = QualificationSubmission::where('qualification_id', $request->id)->count();

                // if($submissions_ > 0) {
                //     $existingUnits = QualificationUnit::where('qualification_id', $request->id)
                //     ->pluck('id')
                //     ->toArray();

                //     if(!array_intersect($newUnit_, $existingUnits)) {
                //         return response()->json([
                //             'message' => 'Validation errors',
                //             'error' => 'You cannot delete existing unit!'
                //         ], 422);
                //     } else {
                //         $existingLO = QualificationLo::where('qualification_id', $request->id)
                //         ->pluck('id')
                //         ->toArray();

                //         if(!array_intersect($newUnit_, $existingLO)) {
                //             return response()->json([
                //                 'message' => 'Validation errors',
                //                 'error' => 'You cannot delete existing unit!'
                //             ], 422);
                //         }
                //     }
                // }                
                
                // return response()->json([
                //     'message' => 'Validation errors',
                //     'error' => 'Success'
                // ], 422);


                $unitsCollection = collect($units);
                $unit_ids = $unitsCollection->pluck('id');
                $loIds = $unitsCollection->pluck('LO')->flatten(1)->pluck('id');
                $acIds = $unitsCollection->flatMap(function ($unit) {
                    return collect($unit['LO'])->flatMap(function ($lo) {
                        return collect($lo['AC'])->pluck('id');
                    });
                });

                

                if (!empty($unit_ids) && isset($request->id)) {
                    $qu = QualificationUnit::whereNotIn('id', $unit_ids)->where('qualification_id', $request->id);
                    $d_qu_ids = $qu->pluck('id');
                    if (!$d_qu_ids->isEmpty()) {
                        $u_lo = QualificationLo::whereIn('unit_id', $d_qu_ids);
                        $d_lo_ids = $u_lo->pluck('id');
                        if (!$d_lo_ids->isEmpty()) {
                            QualificationAc::whereIn('lo_id', $d_lo_ids)->delete();
                        }
                        $u_lo->delete();
                    }
                    $qu->delete();
                }

                if (!empty($loIds) && isset($request->id)) {
                    $u_lo = QualificationLo::whereNotIn('id', $loIds)->where('qualification_id', $request->id);
                    $d_lo_ids = $u_lo->pluck('id');
                    if (!$d_lo_ids->isEmpty()) {
                        QualificationAc::whereIn('lo_id', $d_lo_ids)->delete();
                    }
                    $u_lo->delete();
                }

                if (!empty($acIds) && isset($request->id)) {
                    QualificationAc::whereNotIn('id', $acIds)->where('qualification_id', $request->id)->delete();
                }

                foreach ($units as $unitData) {
                    if (Arr::has($unitData, 'id')) {
                        $unit = QualificationUnit::where('id', $unitData['id'])->first();
                        $unit->qualification_id = $qualification ? $qualification->id : 0;
                        $unit->unit_number = $unitData['unit_number'];
                        $unit->unit_title = $unitData['unit_title'];
                        $unit->unit_type_id = $unitData['unit_type_id'];
                        // $unit->created_by = Auth::id();
                        $unit->updated_by = Auth::id();
                        $unit->save();
                    } else {
                        $unit = QualificationUnit::create([
                            'qualification_id' => $qualification ? $qualification->id : 0,
                            'unit_number' => $unitData['unit_number'],
                            'unit_title' => $unitData['unit_title'],
                            'unit_type_id' => $unitData['unit_type_id'],
                            'status' => 'active',
                            'created_by' => Auth::id(),
                            'updated_by' => Auth::id()
                        ]);
                    }

                    foreach ($unitData['LO'] as $loData) {
                        if (Arr::has($loData, 'id')) {                            
                            $lo = QualificationLo::where('id', $loData['id'])->first();
                            $lo->qualification_id = $qualification ? $qualification->id : 0;
                            $lo->unit_id = $unit ? $unit->id : 0;
                            $lo->lo_number = $loData['lo_number'];
                            $lo->lo_detail = $loData['lo_detail'];
                            // $lo->created_by = Auth::id();
                            $lo->updated_by = Auth::id();
                            $lo->save();
                        } else {
                            $lo = QualificationLo::create([
                                'qualification_id' => $qualification ? $qualification->id : 0,
                                'unit_id' => $unit ? $unit->id : 0,
                                'lo_number' => $loData['lo_number'],
                                'lo_detail' => $loData['lo_detail'],
                                'status' => 'active',
                                'created_by' => Auth::id(),
                                'updated_by' => Auth::id()
                            ]);
                        }

                        foreach ($loData['AC'] as $acData) {
                            if (Arr::has($acData, 'id')) {
                                $ac = QualificationAc::where('id', $acData['id'])->first();
                                $ac->qualification_id = $qualification ? $qualification->id : 0;
                                $ac->lo_id = $lo ? $lo->id : 0;
                                $ac->ac_number = $acData['ac_number'];
                                $ac->ac_detail = $acData['ac_detail'];
                                // $ac->created_by = Auth::id();
                                $ac->updated_by = Auth::id();
                                $ac->save();
                            } else {
                                QualificationAc::create([
                                    'qualification_id' => $qualification ? $qualification->id : 0,
                                    'lo_id' => $lo ? $lo->id : 0,
                                    'ac_number' => $acData['ac_number'],
                                    'ac_detail' => $acData['ac_detail'],
                                    'status' => 'active',
                                    'created_by' => Auth::id(),
                                    'updated_by' => Auth::id()
                                ]);
                            }
                        }
                    }

                    
                }
            }

            if ($request->unit_document_titles != null) {
                $unit_document_titles = json_decode($request->unit_document_titles, true);

                $documentCollection = collect($unit_document_titles);
                $document_ids = $documentCollection->pluck('id');

                QualificationDocumentTitle::whereNotIn('id', $document_ids)->where('qualification_id', $request->id)->delete();

                foreach ($unit_document_titles as $unit_document_title) {
                    if (Arr::has($unit_document_title, 'id')) {
                        $unit_document = QualificationDocumentTitle::where('id', $unit_document_title['id'])->first();
                        $unit_document->title = $unit_document_title['title'];
                        // $unit_document->created_by = Auth::id();
                        $unit_document->updated_by = Auth::id();
                        $unit_document->save();
                    } else {
                        $unit = QualificationDocumentTitle::create([
                            'qualification_id' => $qualification ? $qualification->id : 0,
                            'title' => $unit_document_title['title'],
                            'status' => 'active',
                            'created_by' => Auth::id(),
                            'updated_by' => Auth::id()
                        ]);
                    }
                }
            }

            return response()->json([
                'message' => 'Update successfully.',
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Creation failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_qualificationsV1(Request $request)
    {
        $query = Qualification::query();

        $currUser = Auth::user();
        //dd($currUser);

        if ($request->has('search')) {
            $searchTerm = $request->input('search');
            $quali__ = Qualification::where('sub_title', 'like', "%$searchTerm%")
                ->orWhere('sub_number', 'like', "%$searchTerm%")->pluck('id');
            $query->whereIn('id', $quali__);
        }

        if((int)$currUser->role_id > 2 && (int)$currUser->role_id != 6) {
            $userQualification = UserQualification::where('user_id', Auth::id())->pluck('qualification_id');

            if((int)Auth::user()->role_id == 3) {
                $query->where('status', 'active');
            }

            $query->whereIn('id', $userQualification);
        }
        
        if (((int)$currUser->role_id == 2 || (int)$currUser->role_id == 6) && $request->has('user_id')) {            
            $query->whereIn('created_by', Helper::getAdmin_ids($request->user_id));
        }

        if ($request->has('company_admin_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id));
        }

        if ($request->has('id')) {
            $query->where('id', $request->id);
        }

        

        //$count = $query->count();

        if($request->isEdit && $request->isEdit == "true") {
            $qualifications = $query->withTrashed()->get();
        } else {
            $qualifications = $query->get();
        }

        if ($qualifications->isEmpty()) {
            return response()->json(['error' => 'No qualifications found.'], 404);
        }

        return response()->json([
            'message' => 'Qualifications',
            'data' => QualificationResource::collection($qualifications),            
        ], 200);
    }

    public function get_qualificationsV2(Request $request)
    {
        $query = Qualification::query();

        $currUser = Auth::user();
        //dd($currUser);

        if ($request->has('search')) {
            $searchTerm = $request->input('search');
            $quali__ = Qualification::where('sub_title', 'like', "%$searchTerm%")
                ->orWhere('sub_number', 'like', "%$searchTerm%")->pluck('id');
            $query->whereIn('id', $quali__);
        }

        if((int)$currUser->role_id > 2 && (int)$currUser->role_id != 6) {
            $userQualification = UserQualification::where('user_id', Auth::id())->pluck('qualification_id');

            if((int)Auth::user()->role_id == 3) {
                $query->where('status', 'active');
            }

            $query->whereIn('id', $userQualification);
        }
        
        if (((int)$currUser->role_id == 2 || (int)$currUser->role_id == 6) && $request->has('user_id')) {            
            $query->whereIn('created_by', Helper::getAdmin_ids($request->user_id));
        }

        if ($request->has('company_admin_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id));
        }

        if ($request->has('id')) {
            $query->where('id', $request->id);
        }

        

        //$count = $query->count();

        if($request->isEdit && $request->isEdit == "true") {
            $qualifications = $query->withTrashed()->get();
        } else {
            $qualifications = $query->get();
        }

        if ($qualifications->isEmpty()) {
            return response()->json(['error' => 'No qualifications found.'], 404);
        }

        return response()->json([
            'message' => 'Qualifications',
            'data' => QualificationDropdownResource_V1::collection($qualifications),            
        ], 200);
    }

    public function get_qualificationsV3(Request $request)
    {
        $query = Qualification::query();

        $currUser = Auth::user();

        if ($request->has('search')) {
            $searchTerm = $request->input('search');
            
            $QualificationSearch = Qualification::where('sub_title', 'like', "%$searchTerm%")
                ->orWhere('sub_number', 'like', "%$searchTerm%")->pluck('id');
                
            $query->whereIn('id', $QualificationSearch);
        }

        if((int)$currUser->role_id > 2 && (int)$currUser->role_id != 6) {
            if($currUser->role_id == 3) {
                $userQualification = UserQualification::where('user_id', Auth::id())->where('status', 'active')->pluck('qualification_id');
            } else {
                $userQualification = UserQualification::where('user_id', Auth::id())->pluck('qualification_id');
            }

            $query->whereIn('id', $userQualification);
        }
        
        if (((int)$currUser->role_id == 2 || (int)$currUser->role_id == 6) && $request->has('user_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->user_id));
        }

        if ($request->has('company_admin_id')) {
            $query->whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id));
        }

        if ($request->has('id')) {
            $query->where('id', $request->id);
        }

        $count = $query->count();

        if ($request->has('page')) {
            $qualifications = $query->paginate(20);
        } else {
            $qualifications = $query->get();
        }

        if ($qualifications->isEmpty()) {
            return response()->json(['error' => 'No qualifications found.'], 404);
        }

        return response()->json([
            'message' => 'Qualifications',
            'data' => QualificationResource_V1::collection($qualifications),
            'count' => $count
        ], 200);
    }

    public function get_qualifications(Request $request)
    {
        $query = Qualification::query();

        $currUser = Auth::user();
        //dd($currUser);

        if ($request->has('search')) {
            $searchTerm = $request->input('search');
            // $query->where('sub_title', 'like', "%$searchTerm%")
            //     ->orWhere('sub_number', 'like', "%$searchTerm%");
            
            $QualificationSearch = Qualification::where('sub_title', 'like', "%$searchTerm%")
                ->orWhere('sub_number', 'like', "%$searchTerm%")->pluck('id');
                
            $query->whereIn('id', $QualificationSearch);
        }

        if((int)$currUser->role_id > 2 && (int)$currUser->role_id != 6) {
            if($currUser->role_id == 3) {
                $userQualification = UserQualification::where('user_id', Auth::id())->where('status', 'active')->pluck('qualification_id');
            } else {
                $userQualification = UserQualification::where('user_id', Auth::id())->pluck('qualification_id');
            }

            $query->whereIn('id', $userQualification);
        }
        
        if (((int)$currUser->role_id == 2 || (int)$currUser->role_id == 6) && $request->has('user_id')) {
            // $query->where('created_by', $request->user_id);
            $query->whereIn('created_by', Helper::getAdmin_ids($request->user_id));
        }

        if ($request->has('company_admin_id')) {
            // $query->where('created_by', $request->company_admin_id);
            $query->whereIn('created_by', Helper::getAdmin_ids($request->company_admin_id));
        }

        if ($request->has('id')) {
            $query->where('id', $request->id);
        }

        $count = $query->count();

        if ($request->has('page')) {
            $qualifications = $query->paginate(20);
        } else {
            $qualifications = $query->get();
        }

        if ($qualifications->isEmpty()) {
            return response()->json(['error' => 'No qualifications found.'], 404);
        }

        return response()->json([
            'message' => 'Qualifications',
            'data' => QualificationResource::collection($qualifications),
            'count' => $count
        ], 200);
    }

    public function get_qualification_by_id(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'qualification_id' => 'required',
            'company_admin_id' => 'required',
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        $qualification = Qualification::whereIn('created_by', (Auth::user()->role_id == 1 ? [Auth::id()] : Helper::getAdmin_ids($request->company_admin_id)))
        ->where('id', $request->qualification_id)
        ->withTrashed()->first();

        if ($qualification == null) {
            return response()->json(['error' => 'No qualifications found.'], 404);
        }

        return response()->json([
            'message' => 'Qualification Detail',
            'data' => new QualificationDetailResource($qualification)
        ], 200);
    }

    public function get_assigned_qualifications(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'user_id' => 'required',
        ]);

        if ($validator->fails()) {
            $response_data = [
                'success' => false,
                'message' => 'Incomplete data provided!',
                'errors' => $validator->errors(),
            ];
            return response()->json($response_data);
        }

        // $qualification = UserQualification::where('user_id', $request->user_id)
        //     ->Join('qualifications', 'qualifications.id', '=', 'user_qualifications.qualification_id')
        //     ->select('qualifications.*');

        $userQualification_ = UserQualification::where('user_id', $request->user_id)->pluck('qualification_id');
        $qualification = Qualification::whereIn('id', $userQualification_)->withTrashed();



        $count = $qualification->count();

        if ($request->has('page')) {
            $qualifications = $qualification->paginate(20);
        } else {
            $qualifications = $qualification->get();
        }

        if ($qualifications->isEmpty()) {
            return response()->json(['error' => 'No qualifications found.'], 404);
        }

        return response()->json([
            'message' => 'Assigned Qualifications',
            'data' => QualificationResource::collection($qualifications),
            'count' => $count
        ], 200);
    }

    public function get_superadmin_qualifications(Request $request)
    {
        $myParent = User::where('id', Auth::id())->first();
        // $myQualificationIds = Qualification::where('created_by', Auth::id())->pluck('sub_title');

        $query = Qualification::query();

        if ($request->has('search')) {
            $searchTerm = $request->input('search');

            $qualifi_ = Qualification::where('sub_title', 'like', "%$searchTerm%")
                ->orWhere('sub_number', 'like', "%$searchTerm%")->pluck('id');
            
            $query->whereIn('id', $qualifi_);
        }

        $query->where('created_by', Auth::id());

        // $query->where('created_by', $myParent->created_by);

        $count = $query->count();

        if ($request->has('page')) {
            $qualifications = $query->paginate(20);
        } else {
            $qualifications = $query->get();
        }

        if ($qualifications->isEmpty()) {
            return response()->json(['error' => 'No qualifications found.'], 404);
        }

        return response()->json([
            'message' => 'Parent Qualifications',
            'data' => SuperAdminQualificationResourceV1::collection($qualifications),
            'count' => $count
        ], 200);
    }

    public function get_parent_qualifications(Request $request)
    {
        // $myParent = User::where('id', Auth::id())->first();
        $myParent = User::where('id', Helper::getCompanyAdminId(Auth::id()))->first();
        $myQualificationIds = Qualification::whereIn('created_by', Helper::getAdmin_ids(Auth::id()))->pluck('sub_title');

        $query = Qualification::whereNotIn('sub_title', $myQualificationIds)->where('created_by', $myParent->created_by);

        if ($request->has('search')) {
            $searchTerm = $request->input('search');
            $qualifi_ = Qualification::where('sub_title', 'like', "%$searchTerm%")
                ->orWhere('sub_number', 'like', "%$searchTerm%")->pluck('id');
                
            $query->whereIn('id', $qualifi_);
        }

        $query->where('created_by', $myParent->created_by);

        $count = $query->count();

        if ($request->has('page')) {
            $qualifications = $query->paginate(20);
        } else {
            $qualifications = $query->get();
        }

        if ($qualifications->isEmpty()) {
            return response()->json(['error' => 'No qualifications found.'], 404);
        }

        return response()->json([
            'message' => 'Parent Qualifications',
            'data' => QualificationResource_V1::collection($qualifications),
            'count' => $count
        ], 200);
    }

    public function delete_qualification(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'id' => 'required|integer|exists:qualifications,id',
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        try {
            // $qualification_exists = QualificationSubmission::where('qualification_id', $request->id)->exists();

            // if ($qualification_exists) {
            //     return response()->json(['error' => 'You cannot delete this qualification because there are submissions against it.'], 403);
            // }

            $qualification = Qualification::find($request->id);

            if ($qualification) {
                $qualification_unit = QualificationUnit::where('qualification_id', $qualification->id);
                $d_qu_ids = $qualification_unit->pluck('id');

                if (!$d_qu_ids->isEmpty()) {
                    $u_lo = QualificationLo::whereIn('unit_id', $d_qu_ids);
                    $d_lo_ids = $u_lo->pluck('id');

                    if (!$d_lo_ids->isEmpty()) {
                        QualificationAc::whereIn('lo_id', $d_lo_ids)->delete();
                    }
                    $u_lo->delete();
                }
                $qualification_unit->delete();
                $qualification->delete();

                QualificationDocumentTitle::where('qualification_id', $request->id)->delete();

                return response()->json(['message' => 'Qualification deleted successfully.'], 200);
            }

            return response()->json(['error' => 'Qualification not found.'], 404);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Failed to delete qualification',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_qualification_submissions(Request $request)
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

        $user = User::where('id', $request->user_id)->where('role_id', '3')->first();

        $userQualification = UserQualification::where('user_id', $request->user_id)
             ->where('qualification_id', $request->qualification_id)->first();

        //$users_with_trash = User::where('user_id', $request->user_id)->where('role_id', '3')->withTrashed()->get();

        // $userQualification = UserQualification::where('user_id', $request->user_id)
        //     ->where('qualification_id', $request->qualification_id)
        //     ->Join('users', 'users.id', '=', 'user_qualifications.user_id')
        //     ->where('users.role_id', '3')
        //     ->select('user_qualifications.*')
        //     ->first();

        if($user == null)
        {
            return response()->json(['error' => 'User not found'], 404);
        }

        if ($userQualification == null) {
            return response()->json(['error' => 'No qualifications found.'], 404);
        }

        return response()->json([
            'message' => 'Qualification Submissions',
            'data' => new QualificationSubmissionResource($userQualification)
        ], 200);
    }

    public function get_qualification_submissions_V2(Request $request)
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

        $user = User::where('id', $request->user_id)->where('role_id', '3')->first();

        $userQualification = UserQualification::where('user_id', $request->user_id)
             ->where('qualification_id', $request->qualification_id)->first();

        if($user == null)
        {
            return response()->json(['error' => 'User not found'], 404);
        }

        if ($userQualification == null) {
            return response()->json(['error' => 'No qualifications found.'], 404);
        }

        return response()->json([
            'message' => 'Qualification Submissions',
            'data' => new QualificationSubmissionResource_V2($userQualification)
        ], 200);
    }

    public function get_qualification_submissions_V3(Request $request)
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

        $user = User::where('id', $request->user_id)->where('role_id', '3')->first();

        $userQualification = UserQualification::where('user_id', $request->user_id)
             ->where('qualification_id', $request->qualification_id)->first();

        if($user == null)
        {
            return response()->json(['error' => 'User not found'], 404);
        }

        if ($userQualification == null) {
            return response()->json(['error' => 'No qualifications found.'], 404);
        }

        return response()->json([
            'message' => 'Qualification Submissions',
            'data' => new QualificationSubmissionResource_V3($userQualification)
        ], 200);
    }

    public function get_submissions(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'user_id' => 'required',
            'qualification_id' => 'required',
            'ac_id' => 'required',
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        $qualificationSubmission = QualificationSubmission::where('qualification_id', $request->qualification_id)
            ->where('created_by', $request->user_id)->where('ac_id', $request->ac_id)
            ->get();

        $user_assessor = UserAssessor::where('user_id', $request->user_id)->first();
        if($user_assessor != null) {
            $assessor_ = User::where('id', $user_assessor->assessor_id)->first();
        }

        $ac = QualificationAc::where('qualification_id', $request->qualification_id)
            ->where('id', $request->ac_id)
            ->first();

        return response()->json([
            'message' => 'Qualification Submissions',
            'data' => [
                'assessor' => ($assessor_ != null ? new UserDropdownResource_V1($assessor_) : null),
                'assessment_criterion' => ($ac == null ? null : new QualificationACSResource($ac)),
                'submission_list' => SubmissionDetailResource::collection($qualificationSubmission)
            ]
        ], 200);
    }

    public function update_submission_status(Request $request) {

        $validator = Validator::make($request->all(), [
            'user_id' => 'required',
            'qualification_id' => 'required',
            'ac_id' => 'required',
            'status' => 'required',
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        try {
            $qualification_submission = QualificationSubmission::where('created_by', $request->user_id)
            ->where('qualification_id', $request->qualification_id)
            ->where('ac_id', $request->ac_id)
            ->orderby('id', 'desc')
            ->first();

            if($qualification_submission != null) {
                $qualification_submission->status = $request->status;
                $qualification_submission->assessor_id = Auth::id();
                $qualification_submission->save();

                SubmissionAttachement::where('created_by', $request->user_id)
                ->where('qualification_id', $request->qualification_id)
                ->where('submission_id', $qualification_submission->id)
                    ->update([
                        'status' => $request->status
                        ]);

                return response()->json([
                    'message' => 'Submission status changed successfully!',
                ], 200);

            } else {
                return response()->json([
                    'message' => 'Submission not found!'
                ], 422);
            }
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function update_submission_iqa_status(Request $request) {

        $validator = Validator::make($request->all(), [
            'user_id' => 'required',
            'qualification_id' => 'required',
            'ac_id' => 'required',
            // 'status' => 'required',
            // 'comments' => 'required',
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        try {

            if($request->status != null) {
                $qualification_submission = QualificationSubmission::where('created_by', $request->user_id)
                ->where('qualification_id', $request->qualification_id)
                ->where('ac_id', $request->ac_id)
                ->orderby('created_at', 'desc')
                ->first();
    
                if($qualification_submission != null) {
                    $qualification_submission->iqa_outcome = $request->status;
                    $qualification_submission->iqa_id = Auth::id();
                    $qualification_submission->iqa_comment = ($request->comments ?? $qualification_submission->iqa_comment);
                    $qualification_submission->save();
    
                    return response()->json([
                        'message' => 'Submission outcome changed successfully!',
                    ], 200);
    
                } else {
                    return response()->json([
                        'message' => 'Submission not found!'
                    ], 422);
                }
            } else {
                if(Auth::user()->role_id != 5) {
                    return response()->json([
                        'message' => 'Only iqa can submit comments!'
                    ], 422);
                }
    
                $submision = QualificationAc::where('qualification_id', $request->qualification_id)
                ->where('id', $request->ac_id)
                ->orderby('id', 'desc')
                ->withTrashed()->first();
    
                if($submision != null) {
                    $comments = [
                        'qualification_id' =>  $request->qualification_id,
                        'learner_id' => $request->user_id,
                        'ac_id' => $request->ac_id,
                        'comments' => $request->comments,
                        'created_by' => Auth::id(),
                        'updated_by' => Auth::id(),
                    ];
        
                    $response_ = IqaComment::create($comments);
                } else {
                    return response()->json([
                        'message' => 'Assessment criterion not found!'
                    ], 422);
                }
    
                return response()->json([
                    'message' => 'Comment save successfully.',
                ], 200);
            }            
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function save_submission(Request $request)
    {
        try {

            $validator = Validator::make($request->all(), [
                'qualification_id' => 'required',
                'unit_id' => 'required',
                'lo_id' => 'required',
                'ac_id' => 'required',
                'comment' => 'required',
            //      'file' => 'max:102400',
            // ], [
            //     'file.max' => 'The file size must not exceed 100 MB.',
            ]
        );

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }
            
            if(Auth::user()->role_id != 3) {
                return response()->json([
                    'message' => 'Only learner can submit the document!'
                ], 422);
            }

            $submission_ = null;
            $existingSubmission = QualificationSubmission::where('qualification_id', $request->qualification_id)
            ->where('unit_id', $request->unit_id)
            ->where('lo_id', $request->lo_id)
            ->where('ac_id', $request->ac_id)
            ->where('status', 'In-progress')
            ->where('created_by', Auth::id())
            ->first();

            if($existingSubmission == null) {
                $qualification_submission = [
                    'qualification_id' =>  $request->qualification_id,
                    'unit_id' => $request->unit_id,
                    'lo_id' => $request->lo_id,
                    'ac_id' => $request->ac_id,
                    'comments' => $request->comment ?? null,
                    'status' => 'In-progress',
                    'created_by' => Auth::id(),
                    'updated_by' => Auth::id(),
                ];
    
                $existingSubmission = QualificationSubmission::create($qualification_submission);
            } else {
                $existingSubmission->comments = ($request->comment ?? $existingSubmission->comments);
                $existingSubmission->save();
            }

            

            if ($request->hasFile('file')) {
                // $total_files = count($request->file('file'));

                $basic_url = 'submissions/' . Auth::id();
                

                foreach($request->file as $curr_file) {
                    $extension = $curr_file->extension();
                    $attachement = $curr_file;
                    $url = Str::random(20) . '.' . $extension;
                    
                    $path = ($basic_url . "/" . $url);
                    Helper::FileUpload($path, $attachement);
                    
                    // chmod(storage_path('app/' . $path), 0775);
    
                    $attachement_ = [
                        'qualification_id' =>  $request->qualification_id,
                        'submission_id' => $existingSubmission->id,
                        'attachement' => $url,
                        'status' => 'active',
                        'created_by' => Auth::id(),
                        'updated_by' => Auth::id(),
                    ];
        
                    $attachement_response = SubmissionAttachement::create($attachement_);
                }
                // chmod(storage_path('app/' . $basic_url), 0775);
            } else {
                return response()->json([
                    'message' => 'something went wrong!'
                ], 422);
            }

            return response()->json([
                'message' => 'Document submitted successfully.',
            ], 200);
       
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function delete_submission(Request $request) {

        $validator = Validator::make($request->all(), [
            'qualification_id' => 'required',
            'submission_id' => 'required',
            'id' => 'required',            
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }
        
        if(Auth::user()->role_id != 3) {
            return response()->json([
                'message' => 'Only learner can delete the document!'
            ], 422);
        }

        try {

            $attachements_ = SubmissionAttachement::where('qualification_id', $request->qualification_id)
            ->where('submission_id', $request->submission_id)
            ->where('id', $request->id)
            ->where('created_by', Auth::id())
            ->delete();

            return response()->json([
                'message' => 'Attachement deleted successfully.',
            ], 200);
       
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }

    }

    public function save_assessor_feedback(Request $request)
    {
        try {

            $validator = Validator::make($request->all(), [
                'qualification_id' => 'required',
                'learner_id' => 'required',
                'lo_id' => 'required',
                'feedback' => 'required',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }
            
            if(Auth::user()->role_id != 4) {
                return response()->json([
                    'message' => 'Only assessor can submit feedback!'
                ], 422);
            }

            $submision = QualificationLo::where('qualification_id', $request->qualification_id)
            ->where('id', $request->lo_id)
            ->orderby('id', 'desc')
            ->withTrashed()->first();

            if($submision != null) {
                $feedback = [
                    'qualification_id' =>  $request->qualification_id,
                    'learner_id' => $request->learner_id,
                    'lo_id' => $request->lo_id,
                    'comments' => $request->feedback,
                    'created_by' => Auth::id(),
                    'updated_by' => Auth::id(),
                ];
    
                $response_ = AssessorFeedback::create($feedback);
            } else {
                return response()->json([
                    'message' => 'Learning outcome not found!'
                ], 422);
            }

            return response()->json([
                'message' => 'Feedback save successfully.',
            ], 200);
       
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_assessor_feedback(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'qualification_id' => 'required',
            'learner_id' => 'required',            
            'lo_id' => 'required',
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        $assessorFeedback = AssessorFeedback::where('qualification_id', $request->qualification_id)
            ->where('learner_id', $request->learner_id)->where('lo_id', $request->lo_id)
            ->get();       

        if(count($assessorFeedback) > 0) {
            return response()->json([
                'message' => 'Assessor Feedback List',
                'data' => AssessorFeedbackResource::collection($assessorFeedback)
            ], 200);
        } else {
            return response()->json(['error' => 'No feedback found.'], 404);
        }        
    }

    public function get_iqa_comment(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'qualification_id' => 'required',
            'learner_id' => 'required',            
            'ac_id' => 'required',
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        $iqaComments = IqaComment::where('qualification_id', $request->qualification_id)
            ->where('learner_id', $request->learner_id)->where('ac_id', $request->ac_id)
            ->get();       

        if(count($iqaComments) > 0) {
            return response()->json([
                'message' => 'IQA Comment List',
                'data' => IQACommentResource::collection($iqaComments)
            ], 200);
        } else {
            return response()->json(['error' => 'No iqa comments found.'], 404);
        }        
    }

    public function save_document(Request $request)
    {
        try {        

            $validator = Validator::make($request->all(), [
                'qualification_id' => 'required',
                'req_document_id' => 'required',
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

            if ($request->file('file')) {
                $extension = $request->file('file')->extension();
                $attachement = $request->file('file');
                $url = Str::random(20) . '.' . $extension;

                $basic_url = 'documents/' . Auth::id();
                $path = ($basic_url . "/" . $url);
                
                
                Helper::FileUpload($path, $attachement);
                
                $qualification_document = QualificationDocument::where('qualification_id', $request->qualification_id)
                ->where('document_title_id', $request->req_document_id)
                ->where('status', 'In-progress')
                ->where('created_by', Auth::id())
                ->first();

                if($qualification_document == null) {
                    $document = [
                        'qualification_id' =>  $request->qualification_id,
                        'document_title_id' => $request->req_document_id,
                        'attachment' => $url,
                        'status' => 'In-progress',
                        'created_by' => Auth::id(),
                        'updated_by' => Auth::id(),
                    ];
        
                    $response_ = QualificationDocument::create($document);
                } else {
                    $qualification_document->attachment = $url;
                    $qualification_document->save();
                }
            }

            return response()->json([
                'message' => 'Document Upload successfully.',
            ], 200);
       
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function update_document_detail(Request $request) {

        $validator = Validator::make($request->all(), [
            'user_id' => 'required',
            'qualification_id' => 'required',
            'document_id' => 'required',
            // 'status' => 'required',
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        try {
            $qualification_documents = QualificationDocument::where('qualification_id', $request->qualification_id)
            ->where('id', $request->document_id)
            ->where('created_by', $request->user_id)->first();

            if($qualification_documents != null && $request->status != null) {
                $qualification_documents->status = $request->status;
                $qualification_documents->updated_by = Auth::id();
                $qualification_documents->save();

                return response()->json([
                    'message' => 'Document status changed successfully!',
                ], 200);

            } else if($qualification_documents != null && $request->comments != null) {
                $qualification_documents->comments = $request->comments;
                $qualification_documents->updated_by = Auth::id();
                $qualification_documents->save();

                return response()->json([
                    'message' => 'Comments saved successfully!',
                ], 200);

            } else if($qualification_documents != null && $request->iqa_status != null) {
                $qualification_documents->iqa_status = $request->iqa_status;
                $qualification_documents->save();

                return response()->json([
                    'message' => 'IQA status changed successfully!',
                ], 200);

            } else if($qualification_documents != null && $request->iqa_comment != null) {
                $qualification_documents->iqa_comment = $request->iqa_comment;
                $qualification_documents->save();

                return response()->json([
                    'message' => 'IQA status changed successfully!',
                ], 200);

            } else if ($qualification_documents != null && $request->file('file')) {


                $extension = $request->file('file')->extension();
                $attachement = $request->file('file');
                $url = Str::random(20) . '.' . $extension;

                $basic_url = 'documents/' . $request->user_id;
                $path = ($basic_url . "/" . $url);                
                
                Helper::FileUpload($path, $attachement);

                $qualification_documents->assessor_attachement = $url;
                $qualification_documents->updated_by = Auth::id();
                $qualification_documents->save();

                return response()->json([
                    'message' => 'Assessor document Upload successfully.',
                ], 200);
            } else {
                return response()->json([
                    'message' => 'Document not found!'
                ], 422);
            }
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'An error occurred',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function superadmin_qualification_transfer(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'id' => 'required|exists:qualifications,id',
        ]);

        if ($validator->fails()) {
            $errors = $validator->errors()->all();
            return response()->json([
                'message' => 'Validation errors',
                'error' => $errors[0]
            ], 422);
        }

        try {
            $qualification = null;
            $unitsAdmin = [];
            $lo_data_admin = [];
            $ac_data_admin = [];

            $qualificationAdmin = Qualification::where('id', $request->id)->first();
            if ($qualificationAdmin) {
                $qualificationData = [
                    'sub_title' => $qualificationAdmin->sub_title ?? null,
                    'sub_number' => $qualificationAdmin->sub_number ?? null,
                    'status' => 'active',
                    'created_by' => Auth::id(),
                    'updated_by' => Auth::id()
                ];

                $qualification =  Qualification::create($qualificationData);

                $unitsAdmin = QualificationUnit::where('qualification_id', $qualificationAdmin->id)->get();
            }

            if (count($unitsAdmin) > 0) {
                foreach ($unitsAdmin as $unitData) {
                    $unit = QualificationUnit::create([
                        'qualification_id' => $qualification ? $qualification->id : 0,
                        'unit_number' => $unitData['unit_number'],
                        'unit_title' => $unitData['unit_title'],
                        'unit_type_id' => $unitData['unit_type_id'],
                        'status' => 'active',
                        'created_by' => Auth::id(),
                        'updated_by' => Auth::id()
                    ]);

                    $lo_data_admin = QualificationLo::where('unit_id', $unitData['id'])->get();

                    if (count($lo_data_admin) > 0) {
                        foreach ($lo_data_admin as $loData) {
                            $lo = QualificationLo::create([
                                'qualification_id' => $qualification ? $qualification->id : 0,
                                'unit_id' => $unit ? $unit->id : 0,
                                'lo_number' => $loData['lo_number'],
                                'lo_detail' => $loData['lo_detail'],
                                'status' => 'active',
                                'created_by' => Auth::id(),
                                'updated_by' => Auth::id()
                            ]);

                            $ac_data_admin = QualificationAc::where('lo_id', $loData['id'])->get();

                            foreach ($ac_data_admin as $acData) {
                                QualificationAc::create([
                                    'qualification_id' => $qualification ? $qualification->id : 0,
                                    'lo_id' => $lo ? $lo->id : 0,
                                    'ac_number' => $acData['ac_number'],
                                    'ac_detail' => $acData['ac_detail'],
                                    'status' => 'active',
                                    'created_by' => Auth::id(),
                                    'updated_by' => Auth::id()
                                ]);
                            }
                        }
                    }
                }
            }

            $unit_document_titles_admin = QualificationDocumentTitle::where('qualification_id', $request->id)->get();

            if (count($unit_document_titles_admin) > 0) {
                foreach ($unit_document_titles_admin as $unit_document_title) {
                    $unit = QualificationDocumentTitle::create([
                        'qualification_id' => $qualification ? $qualification->id : 0,
                        'title' => $unit_document_title['title'],
                        'status' => 'active',
                        'created_by' => Auth::id(),
                        'updated_by' => Auth::id()
                    ]);
                }
            }

            return response()->json([
                'message' => 'Transfer successfully.',
            ], 201);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Creation failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function get_documents(Request $request)
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

        $qualificationSubmission = QualificationDocumentTitle::where('qualification_id', $request->qualification_id)
            ->select('qualification_document_titles.*', DB::raw($request->user_id . ' as user_id'))
            ->get();


        return response()->json([
            'message' => 'Qualification Documents',
            'data' => QualificationDocumentResource::collection($qualificationSubmission)
        ], 200);
    }

    public function tt(Request $request)
    {
        // $attachment = Str::uuid() . "." . $request->file->extension();

        // $data = [
        //     'filePath' => 'customer/' . $attachment,
        //     'file' => $request->file,
        //     'type' => 'public'
        // ];

        $result = Helper::FileUpload("minutes_of_meetings/123.png" , null);
        return $result;
    }
}
