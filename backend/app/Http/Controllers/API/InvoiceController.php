<?php

namespace App\Http\Controllers\API;

use App\Http\Controllers\Controller;
use App\Http\Helpers\Helper;
use App\Http\Resources\AssessorDocumenResource;
use App\Http\Resources\RoleResource;
use App\Http\Resources\UserResource;
use App\Http\Resources\CommunicationResource;
use App\Http\Resources\CustomerResource;
use App\Http\Resources\InvoiceDetailsResource;
use App\Http\Resources\InvoiceResource;
use App\Http\Resources\UserLoginResource;
use App\Http\Resources\UserNameResource;
use App\Imports\LearnerImport;
use App\Imports\UsersImport;
use App\Mail\BulkEditUserMail;
use App\Models\AssessorDocument;
use App\Models\Communication;
use App\Models\Customer;
use App\Models\Invoice;
use App\Models\InvoiceDetail;
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
use Barryvdh\DomPDF\Facade\Pdf;
use Carbon\Carbon;
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

class InvoiceController extends Controller
{
    public function generate_invoice_job(Request $request)
    {
        $customers = Customer::get();

        foreach($customers as $customer) {
            $companyAdmin = User::where('customer_id', $customer->id)
            ->where('role_id', '2')->first();

            if($companyAdmin != null) {
                
                //Get All Learners
                $user_qualifications = UserQualification::join('invoice_details', function($join) {
                  $join->on('user_qualifications.user_id', '=', 'invoice_details.learner_id');
                  $join->on('user_qualifications.qualification_id', '=', 'invoice_details.qualification_id');
                })->leftJoin('users', function($join) {
                  $join->on('user_qualifications.user_id', '=', 'users.id');
                })->where('users.role_id', 3)->whereIn('user_qualifications.created_by', Helper::getAdmin_ids($companyAdmin->id))
                ->select('user_qualifications.*')->pluck('id');
                
                //Get Unpaid Learners
                $invoice_ = UserQualification::leftJoin('users', function($join) {
                  $join->on('user_qualifications.user_id', '=', 'users.id');
                })->where('users.role_id', 3)->whereIn('user_qualifications.created_by', Helper::getAdmin_ids($companyAdmin->id))
                ->whereNotIn('user_qualifications.id', $user_qualifications)
                ->select('user_qualifications.*')->get();
                
                $totalLearners_ = count($invoice_);
                if($totalLearners_ > 0) {
                    $invoice_no = 'INV' . date('Ymd') . '-' . Str::upper(Str::random(6));
                    
                    //Create Invoice
                    $create_invoice_data = [
                        'invoice_no' => $invoice_no,
                        'date' => Carbon::now(),
                        'registered_learners' => $totalLearners_,
                        'customer_id' => $customer->id,
                    ];
        
                    $invoice = Invoice::create($create_invoice_data);
                    
                    if($invoice) {
                       
                        //Create Invoice Detail
                        foreach ($invoice_ as $learner) {
                            $create_invoice_detail = [
                                'invoice_no' => $invoice->invoice_no,
                                'learner_id' => $learner->user_id,
                                'qualification_id' => $learner->qualification_id,
                                'customer_id' => $invoice->customer_id,
                            ];
                            
                            InvoiceDetail::create($create_invoice_detail);
                        }

                        //Send Invoice
                        $invoice_data = [
                            'invoice_no' => $invoice->invoice_no
                        ];

                        $invoice_response = Helper::generateInvoicePDF($invoice_data);
                        if (is_string($invoice_response)) {                            
                        } else {
                            
                            $pdf = Pdf::loadView('pdf.invoice_pdf', ['data' => $invoice_response]);
                            $content = $pdf->download()->getOriginalContent();                            
                            $path = ('invoices/' . $invoice->invoice_no . '.pdf');
                            Helper::FileUpload_WithoutAuth($path, $content, $customer->id);
                            // Storage::disk('local')->put(
                            //     '/public/invoices/' . $invoice->customer_id . '/' . $invoice->invoice_no . '.pdf',
                            //     $content
                            // );                            
                        }                        
                    }
                }
            }




        }

        return response()->json([
            'message' => 'Job complete successfully!',
        ], 200);
    }

    public function get_invoices(Request $request)
    {
        try {

            $role_id = Auth::user()->role_id;
            $customerId = 0;

            if ($role_id == "2") {
                $customerId = Auth::user()->customer_id;
            } else {
                $validator = Validator::make($request->all(), [
                    'customer_id' => 'required',
                ]);

                if ($validator->fails()) {
                    $errors = $validator->errors()->all();
                    return response()->json([
                        'message' => 'Validation errors',
                        'error' => $errors[0]
                    ], 422);
                }

                $customerId = $request->customer_id;
            }



            $data = Invoice::where('customer_id', $customerId);

            if ($request->status) {
                $data = $data->where('status', $request->status);
            }

            $data = $data->orderby('created_at', 'desc')->get();

            if (count($data) > 0) {
                return response()->json([
                    'message' => 'Invoice List',
                    'data' => InvoiceResource::collection($data),
                ], 200);
            } else {
                return response()->json([
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

    public function get_invoice_detail(Request $request)
    {
        try {

            $validator = Validator::make($request->all(), [
                'invoice_no' => 'required',
            ]);

            if ($validator->fails()) {
                $errors = $validator->errors()->all();
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $errors[0]
                ], 422);
            }

            $invoice_details = InvoiceDetail::where('invoice_no', $request->invoice_no)->get();

            if (count($invoice_details) > 0) {
                return response()->json([
                    'message' => 'Invoice Detail',
                    'data' => InvoiceDetailsResource::collection($invoice_details),
                ], 200);
            } else {
                return response()->json([
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

    public function action_invoice_status(Request $request)
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

            $invoice = Invoice::where('id', $request->id)->first();

            if ($invoice != null) {
                if ($request->status == 'deleted') {
                    $invoice->status = $request->status;
                    $invoice->delete();
                } else {
                    $invoice->status = $request->status;
                }

                $invoice->save();
            }

            return response()->json([
                'message' => 'Invoice ' . $request->status . ' Successfully',
                'data' => new InvoiceResource($invoice)
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Failed to change',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function action_learner_status(Request $request)
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

            // $ids = explode(',', $request->ids);

            // if (count($ids) > 0) {

            $userQualification = UserQualification::where('id', $request->id)->first();            

            if ($userQualification != null) {
                $userQualification->status = ($request->status == "inactive" ? "deactive" : $request->status);
                $userQualification->save();

                //User Inactive
                $userQualificationCount = UserQualification::where('user_id', $userQualification->user_id)->where('status', 'active')->count();

                $user_ = User::where('id', $userQualification->user_id)->first();
                $user_->status = ($userQualificationCount > 0 ? "active" : "inactive");
                $user_->save();
                
                $invoiceDetail = InvoiceDetail::where('learner_id', $userQualification->user_id)
                    ->where('qualification_id', $userQualification->qualification_id)->first();

                if ($invoiceDetail != null) {
                    $invoiceDetail->status = $request->status;
                    $invoiceDetail->save();
                }
            }
            // }

            $responseMessage = ($request->status == "inactive" ? "Deactivated" : $request->status);
            return response()->json([
                'message' => 'Learner ' . $responseMessage . ' Successfully',
            ], 200);
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Failed to change',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    public function generate_invoice_pdf(Request $request)
    {
        try {
            $validator = Validator::make($request->all(), [
                'invoice_no' => 'required',
            ]);

            if ($validator->fails()) {
                return response()->json([
                    'message' => 'Validation errors',
                    'error' => $validator->errors()->first(),
                ], 422);
            }

            $invoice_data = [
                'invoice_no' => $request->invoice_no
            ];

            $invoice_response = Helper::generateInvoicePDF($invoice_data);
            if (is_string($invoice_response)) {
                return response()->json([
                    'message' => $invoice_response,
                ], 404);
            }

        //  return view('pdf.invoice_pdf', ['data' => $invoice_response]);

            $invoice_detail_ = Invoice::where('invoice_no', $request->invoice_no)->first();

            $pdf = Pdf::loadView('pdf.invoice_pdf', ['data' => $invoice_response]);

             $content = $pdf->download()->getOriginalContent();
            //  Storage::put('public/bills/bubla.pdf',$content);
             


            $path = ('invoices/' . $request->invoice_no . '.pdf');
            Helper::FileUpload_WithoutAuth($path, $content, ($invoice_detail_ != null ? $invoice_detail_->customer_id : 0));

            //  Storage::disk('local')->put(
            //     '/public/invoices/' . $request->invoice_no . '.pdf',
            //     $content
            // );
             

            // return $pdf->download('invoice.pdf');
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    // public function generate_invoice_pdf(Request $request)
    // {
    //     // return view('pdf.invoice_pdf');

    //     try {
    //         $validator = Validator::make($request->all(), [
    //             'invoice_no' => 'required',
    //         ]);

    //         if ($validator->fails()) {
    //             $errors = $validator->errors()->all();
    //             return response()->json([
    //                 'message' => 'Validation errors',
    //                 'error' => $errors[0]
    //             ], 422);
    //         }

    //         $invoice_data = [
    //             'invoice_no' => $request->invoice_no
    //         ];

    //         // $data = [
    //         //     [
    //         //         'quantity' => 1,
    //         //         'description' => '1 Year Subscription',
    //         //         'price' => '129.00'
    //         //     ]
    //         // ];

    //         $invoice_response = Helper::generateInvoicePDF($invoice_data);

    //         $pdf = Pdf::loadView('pdf.invoice_pdf', ['data' => $invoice_response]);

    //         return $pdf->download();

    //         return $invoice_response;
    //     } catch (\Exception $e) {
    //         return response()->json([
    //             'message' => 'Failed',
    //             'error' => $e->getMessage(),
    //         ], 500);
    //     }
    // }
}
