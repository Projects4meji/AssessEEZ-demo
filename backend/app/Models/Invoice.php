<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class Invoice extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'invoice_no',
        'date',
        'registered_learners',
        'status',
        'created_at',
        'updated_at',
        'deleted_at',
        'customer_id'
    ];
}
