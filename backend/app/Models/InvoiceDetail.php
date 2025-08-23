<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class InvoiceDetail extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'invoice_no',
        'learner_id',
        'qualification_id',
        'status',
        'created_at',
        'updated_at',
        'deleted_at',
        'customer_id'
    ];
}
